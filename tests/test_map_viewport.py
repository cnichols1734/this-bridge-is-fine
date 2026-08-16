from types import SimpleNamespace

import backend.api as api
from backend.api import _map_mode, _query_viewport_bridges, create_app
from backend.config import Config


US_BBOX = "-125,24,-66,50"
EMPTY_BBOX = "-40,0,-30,10"
OCEAN = (-40.0, 0.0, -30.0, 10.0)
WIDE = (-125.0, 24.0, -66.0, 50.0)


class DummyDB:
    def close(self):
        pass

    def query(self, _model):
        raise AssertionError("viewport tests must use _fetch_map_bridges")


def _bridge(**kw):
    defaults = dict(
        state_code="17",
        structure_number="1",
        lat=41.88,
        lng=-87.63,
        bridge_condition="P",
        lowest_rating=4,
        unease_score=40,
        status_code="A",
    )
    defaults.update(kw)
    return SimpleNamespace(**defaults)


def _in_bbox(bridge, bbox):
    west, south, east, north = bbox
    return west <= bridge.lng <= east and south <= bridge.lat <= north


def _fetch_from(fixtures):
    def fetch(db, bbox, *, condition=None, exclude_condition=None, limit):
        rows = [row for row in fixtures if _in_bbox(row, bbox)]
        if condition is not None:
            rows = [row for row in rows if row.bridge_condition == condition]
        if exclude_condition is not None:
            rows = [row for row in rows if row.bridge_condition != exclude_condition]
        rows = sorted(rows, key=lambda row: row.unease_score or 0, reverse=True)
        return rows[:limit]

    return fetch


FIXTURES = [
    _bridge(
        structure_number="CA-POOR",
        state_code="06",
        lat=37.77,
        lng=-122.42,
        bridge_condition="P",
        unease_score=22,
    ),
    _bridge(
        structure_number="NY-POOR",
        state_code="36",
        lat=40.71,
        lng=-74.01,
        bridge_condition="P",
        unease_score=18,
    ),
    _bridge(
        structure_number="TX-POOR",
        state_code="48",
        lat=29.76,
        lng=-95.37,
        bridge_condition="P",
        unease_score=15,
    ),
    _bridge(
        structure_number="IL-GOOD",
        state_code="17",
        lat=41.88,
        lng=-87.63,
        bridge_condition="G",
        lowest_rating=8,
        unease_score=95,
    ),
    _bridge(
        structure_number="IL-FAIR",
        state_code="17",
        lat=41.90,
        lng=-87.65,
        bridge_condition="F",
        lowest_rating=5,
        unease_score=90,
    ),
    *[
        _bridge(
            structure_number=f"BUSY-{i}",
            state_code="17",
            lat=41.8 + i * 0.01,
            lng=-87.6,
            bridge_condition="G",
            lowest_rating=7,
            unease_score=99 - i,
        )
        for i in range(8)
    ],
]


def _client(monkeypatch, fixtures=FIXTURES, cap=None):
    monkeypatch.setattr(api, "_session", lambda: DummyDB())
    monkeypatch.setattr(api, "_fetch_map_bridges", _fetch_from(fixtures))
    if cap is not None:
        monkeypatch.setattr(Config, "MAP_FEATURE_CAP", cap)
    return create_app().test_client()


def _features(client, bbox, zoom):
    response = client.get(f"/api/bridges?bbox={bbox}&zoom={zoom}")
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["type"] == "FeatureCollection"
    return payload


def _conditions(payload):
    return [feature["properties"]["condition"] for feature in payload["features"]]


def _ids(payload):
    return [feature["properties"]["id"] for feature in payload["features"]]


def test_map_mode_thresholds():
    assert _map_mode(4) == "poor_only"
    assert _map_mode(4.9) == "poor_only"
    assert _map_mode(5) == "poor_first"
    assert _map_mode(6) == "poor_first"
    assert _map_mode(7.9) == "poor_first"
    assert _map_mode(8) == "mixed"
    assert _map_mode(11) == "mixed"


def test_zoom_4_returns_poor_in_wide_bbox(monkeypatch):
    payload = _features(_client(monkeypatch), US_BBOX, 4)
    conditions = _conditions(payload)
    assert conditions
    assert set(conditions) == {"P"}
    assert "06-CA-POOR" in _ids(payload)
    assert "36-NY-POOR" in _ids(payload)
    assert "hint" not in payload


def test_zoom_6_returns_poor_in_wide_bbox(monkeypatch):
    payload = _features(_client(monkeypatch), US_BBOX, 6)
    ids = _ids(payload)
    assert "06-CA-POOR" in ids
    assert "36-NY-POOR" in ids
    assert "48-TX-POOR" in ids
    assert "P" in _conditions(payload)


def test_zoom_11_returns_mixed_conditions(monkeypatch):
    payload = _features(_client(monkeypatch), US_BBOX, 11)
    assert {"G", "F", "P"} <= set(_conditions(payload))


def test_empty_bbox_is_empty(monkeypatch):
    payload = _features(_client(monkeypatch), EMPTY_BBOX, 4)
    assert payload["features"] == []
    assert payload["count"] == 0
    assert payload["capped"] is False

    payload = _features(_client(monkeypatch), EMPTY_BBOX, 11)
    assert payload["features"] == []


def test_missing_bbox_is_still_an_error():
    response = create_app().test_client().get("/api/bridges?zoom=4")
    assert response.status_code == 400


def test_cap_is_honored_at_low_zoom(monkeypatch):
    payload = _features(_client(monkeypatch, cap=2), US_BBOX, 4)
    assert len(payload["features"]) == 2
    assert payload["capped"] is True
    assert payload["count"] == 2
    assert set(_conditions(payload)) == {"P"}


def test_poor_survives_cap_that_would_be_all_high_unease(monkeypatch):
    """Quiet Poor must not lose to busy Good/Fair when zoomed out."""
    monkeypatch.setattr(api, "_fetch_map_bridges", _fetch_from(FIXTURES))
    rows, capped = _query_viewport_bridges(DummyDB(), WIDE, 6, cap=3)
    conditions = [row.bridge_condition for row in rows]
    assert conditions.count("P") == 3
    assert capped is False

    city_rows, _city_capped = _query_viewport_bridges(DummyDB(), WIDE, 11, cap=3)
    city_conditions = [row.bridge_condition for row in city_rows]
    assert "P" not in city_conditions
    assert set(city_conditions) <= {"G", "F"}

    payload = _features(_client(monkeypatch, cap=3), US_BBOX, 6)
    assert set(_conditions(payload)) == {"P"}
    city = _features(_client(monkeypatch, cap=3), US_BBOX, 11)
    assert "P" not in _conditions(city)


def test_state_zoom_fills_remaining_cap_with_others(monkeypatch):
    monkeypatch.setattr(api, "_fetch_map_bridges", _fetch_from(FIXTURES))
    rows, capped = _query_viewport_bridges(DummyDB(), WIDE, 6, cap=5)
    conditions = [row.bridge_condition for row in rows]
    assert conditions.count("P") == 3
    assert len(rows) == 5
    assert set(conditions) - {"P"}
    assert capped is True


def test_continental_zoom_stays_poor_only_even_with_room(monkeypatch):
    monkeypatch.setattr(api, "_fetch_map_bridges", _fetch_from(FIXTURES))
    rows, capped = _query_viewport_bridges(DummyDB(), WIDE, 4, cap=20)
    assert {row.bridge_condition for row in rows} == {"P"}
    assert len(rows) == 3
    assert capped is False


def test_empty_bbox_query_helper_is_empty(monkeypatch):
    monkeypatch.setattr(api, "_fetch_map_bridges", _fetch_from(FIXTURES))
    rows, capped = _query_viewport_bridges(DummyDB(), OCEAN, 6, cap=10)
    assert rows == []
    assert capped is False
