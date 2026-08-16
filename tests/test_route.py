from types import SimpleNamespace

import backend.api as api
from backend.api import create_app
from backend.config import Config
from backend.route import (
    collect_route_roads,
    extract_steps,
    filter_on_drive,
    osrm_route_url,
    parse_lonlat,
    pick_worst_on_drive,
    road_keys,
    roads_match,
    route_summary,
    select_route_bridges,
)


def _row(**kw):
    defaults = dict(
        bridge_condition="G",
        unease_score=10,
        along=0.5,
    )
    defaults.update(kw)
    return SimpleNamespace(**defaults)


def test_osrm_url_uses_configured_base():
    url = osrm_route_url((-87.63, 41.88), (-87.68, 42.05), base="https://router.example")
    assert url.startswith("https://router.example/route/v1/driving/")
    assert "geometries=geojson" in url
    assert "steps=true" in url


def test_parse_lonlat():
    assert parse_lonlat("-87.63,41.88") == (-87.63, 41.88)
    assert parse_lonlat("  -87.63 , 41.88 ") == (-87.63, 41.88)
    assert parse_lonlat("181,0") is None
    assert parse_lonlat("0,91") is None
    assert parse_lonlat("1") is None
    assert parse_lonlat("a,b") is None
    assert parse_lonlat("") is None
    assert parse_lonlat(None) is None


def test_summary_counts_every_condition():
    rows = [
        _row(bridge_condition="P"),
        _row(bridge_condition="P"),
        _row(bridge_condition="F"),
        _row(bridge_condition="G"),
        _row(bridge_condition=None),
    ]
    summary = route_summary(rows)
    assert summary == {
        "bridges": 5,
        "poor": 2,
        "fair": 1,
        "good": 1,
        "unknown": 1,
    }


def test_empty_buffer_is_empty():
    assert route_summary([]) == {
        "bridges": 0,
        "poor": 0,
        "fair": 0,
        "good": 0,
        "unknown": 0,
    }
    listed, capped = select_route_bridges([], cap=10)
    assert listed == []
    assert capped is False


def test_poor_listed_first_then_along_the_drive():
    rows = [
        _row(bridge_condition="G", along=0.1, unease_score=1),
        _row(bridge_condition="P", along=0.9, unease_score=40),
        _row(bridge_condition="F", along=0.2, unease_score=20),
        _row(bridge_condition="P", along=0.3, unease_score=30),
    ]
    listed, capped = select_route_bridges(rows, cap=10)
    assert capped is False
    assert [row.bridge_condition for row in listed] == ["P", "P", "G", "F"]
    assert listed[0].along == 0.3
    assert listed[1].along == 0.9


def test_cap_never_drops_poor():
    poor = [
        _row(bridge_condition="P", along=i / 10, unease_score=50 - i)
        for i in range(6)
    ]
    others = [
        _row(bridge_condition="G", along=0.05 + i / 20, unease_score=90)
        for i in range(8)
    ]
    listed, capped = select_route_bridges(poor + others, cap=4)
    assert [row.bridge_condition for row in listed] == ["P"] * 6
    assert len(listed) == 6
    assert capped is True
    summary = route_summary(poor + others)
    assert summary["poor"] == 6
    assert summary["bridges"] == 14


def test_cap_fills_remaining_with_others_after_poor():
    poor = [_row(bridge_condition="P", along=0.8, unease_score=40)]
    others = [
        _row(bridge_condition="G", along=0.1, unease_score=10),
        _row(bridge_condition="F", along=0.4, unease_score=20),
        _row(bridge_condition="G", along=0.9, unease_score=5),
    ]
    listed, capped = select_route_bridges(poor + others, cap=3)
    assert [row.bridge_condition for row in listed] == ["P", "G", "F"]
    assert listed[1].along == 0.1
    assert capped is True


def test_road_keys_normalize_highways_and_streets():
    assert "I90" in road_keys("INTERSTATE 90")
    assert "I90" in road_keys("I-90")
    assert "I45" in road_keys("IH 45 NB")
    assert "I45" in road_keys("Interstate 45")
    assert "US59" in road_keys("US HIGHWAY 59")
    assert "US59" in road_keys("US 59")
    assert "SH288" in road_keys("SH 288")
    assert "SH288" in road_keys("TX 288")
    assert "FM1960" in road_keys("FARM TO MARKET 1960")
    assert "FM1960" in road_keys("FM 1960")
    assert "ALABAMA ST" in road_keys("W ALABAMA ST")
    assert "ALABAMA ST" in road_keys("West Alabama Street")
    assert "LAKE SHORE DR" in road_keys("LAKE SHORE DRIVE")
    assert "LAKE SHORE DR" in road_keys("Lake Shore Drive")


def test_on_the_drive_is_facility_not_feature_crossed():
    on_i45 = _row(facility_carried="IH 45", feature_crossed="MAIN ST")
    overpass = _row(facility_carried="INTERSTATE 45", feature_crossed="MAIN STREET")
    surface = _row(facility_carried="W ALABAMA ST", feature_crossed="BUFFALO BAYOU")
    river = _row(facility_carried="US HIGHWAY 59", feature_crossed="BUFFALO BAYOU")

    i45_roads = ["Interstate 45", "I 45"]
    assert roads_match(on_i45.facility_carried, i45_roads)
    assert not roads_match(on_i45.feature_crossed, i45_roads)

    main_roads = ["Main Street", "West Alabama Street"]
    kept = filter_on_drive([on_i45, overpass, surface, river], main_roads)
    assert [row.facility_carried for row in kept] == ["W ALABAMA ST"]

    kept_i45 = filter_on_drive([on_i45, overpass, surface, river], i45_roads)
    assert {row.facility_carried for row in kept_i45} == {"IH 45", "INTERSTATE 45"}


def test_going_under_an_overpass_is_not_on_the_drive():
    overpass = _row(facility_carried="INTERSTATE 90", feature_crossed="MAIN ST")
    span = _row(facility_carried="MAIN STREET", feature_crossed="CHICAGO RIVER")
    kept = filter_on_drive([overpass, span], ["Main Street"])
    assert [row.facility_carried for row in kept] == ["MAIN STREET"]


def test_nameless_osrm_does_not_resurrect_overpasses():
    """No road names must not fall back to the 150 m set.

    I-90 over Main Street sits on the same 2D point as the surface road.
    A spatial fallback would paint the overpass you go under.
    """
    overpass = _row(facility_carried="INTERSTATE 90", feature_crossed="MAIN ST")
    span = _row(facility_carried="MAIN STREET", feature_crossed="CHICAGO RIVER")
    assert filter_on_drive([overpass, span], []) == []
    assert filter_on_drive([overpass, span], ["", " "]) == []


def test_collect_route_roads_reads_name_and_ref():
    osrm = {
        "legs": [
            {
                "steps": [
                    {"name": "Interstate 45", "ref": "I 45;US 59"},
                    {"name": "Main Street", "ref": ""},
                    {"name": "Interstate 45", "ref": "I 45"},
                ]
            }
        ]
    }
    assert collect_route_roads(osrm) == ["Interstate 45", "I 45", "US 59", "Main Street"]


def test_extract_steps_keeps_maneuvers():
    osrm = {
        "legs": [
            {
                "steps": [
                    {
                        "name": "Lake Shore Drive",
                        "ref": "",
                        "distance": 400,
                        "duration": 32,
                        "maneuver": {
                            "type": "turn",
                            "modifier": "right",
                            "location": [-87.62, 41.88],
                        },
                    }
                ]
            }
        ]
    }
    steps = extract_steps(osrm)
    assert steps[0]["type"] == "turn"
    assert steps[0]["modifier"] == "right"
    assert steps[0]["name"] == "Lake Shore Drive"
    assert steps[0]["distance_m"] == 400
    assert steps[0]["location"] == [-87.62, 41.88]


def test_top_three_worst_are_poor_then_lowest_score():
    rows = [
        _row(bridge_condition="G", unease_score=90, lowest_rating=8, id="g-ok"),
        _row(bridge_condition="F", unease_score=75, lowest_rating=5, id="f-mid"),
        _row(bridge_condition="P", unease_score=50, lowest_rating=4, id="p-quiet"),
        _row(bridge_condition="P", unease_score=30, lowest_rating=3, id="p-bad"),
        _row(bridge_condition="G", unease_score=70, lowest_rating=7, id="g-busy"),
        _row(bridge_condition="F", unease_score=95, lowest_rating=6, id="f-ok"),
    ]
    worst = pick_worst_on_drive(rows, 3)
    assert [row.id for row in worst] == ["p-bad", "p-quiet", "g-busy"]


def test_summary_stays_complete_when_list_is_capped():
    rows = [
        *[_row(bridge_condition="P", along=i / 20) for i in range(3)],
        *[_row(bridge_condition="G", along=0.5 + i / 20) for i in range(10)],
    ]
    listed, capped = select_route_bridges(rows, cap=5)
    summary = route_summary(rows)
    assert capped is True
    assert len(listed) == 5
    assert summary["bridges"] == 13
    assert summary["poor"] == 3
    assert summary["good"] == 10


class DummyDB:
    def close(self):
        pass

    def query(self, _model):
        raise AssertionError("drive tests must use _fetch_route_bridges")


def _client(monkeypatch, *, route=None, matches=None, error=None):
    monkeypatch.setattr(api, "_session", lambda: DummyDB())
    if error is not None:
        def boom(*_args, **_kwargs):
            raise error

        monkeypatch.setattr(api, "fetch_osrm_route", boom)
    else:
        monkeypatch.setattr(
            api,
            "fetch_osrm_route",
            lambda *_args, **_kwargs: route
            or {
                "geometry": {
                    "type": "LineString",
                    "coordinates": [[-87.63, 41.88], [-87.68, 42.05]],
                },
                "distance_m": 22116.6,
                "duration_s": 1574.1,
                "steps": [],
                "roads": [],
            },
        )
    monkeypatch.setattr(api, "_fetch_route_bridges", lambda *_args, **_kwargs: matches or [])
    return create_app().test_client()


def test_drive_requires_two_points():
    client = create_app().test_client()
    assert client.get("/api/drive").status_code == 400
    assert client.get("/api/drive?from=-87.63,41.88").status_code == 400
    same = client.get("/api/drive?from=-87.63,41.88&to=-87.63,41.88")
    assert same.status_code == 400


def test_drive_returns_route_and_empty_buffer(monkeypatch):
    payload = _client(monkeypatch).get(
        "/api/drive?from=-87.6298,41.8781&to=-87.6847,42.0451"
    ).get_json()
    assert payload["route"]["distance_m"] == 22116.6
    assert payload["route"]["duration_s"] == 1574.1
    assert payload["route"]["geometry"]["type"] == "LineString"
    assert payload["summary"]["bridges"] == 0
    assert payload["summary"]["poor"] == 0
    assert payload["summary"]["capped"] is False
    assert payload["bridges"] == []


def test_drive_lists_poor_first_and_keeps_full_counts(monkeypatch):
    matches = [
        (
            SimpleNamespace(
                id=1,
                state_code="17",
                structure_number="GOOD",
                lat=41.9,
                lng=-87.65,
                bridge_condition="G",
                lowest_rating=8,
                unease_score=5,
                along=0.1,
                status_code="A",
                status_label="Open",
                headline=None,
                facility_carried="I-90",
                feature_crossed="River",
                adt=40000,
                adt_suspect=False,
                year_built=1998,
                why=None,
            ),
            12.0,
        ),
        (
            SimpleNamespace(
                id=2,
                state_code="17",
                structure_number="POOR",
                lat=41.95,
                lng=-87.66,
                bridge_condition="P",
                lowest_rating=4,
                unease_score=40,
                along=0.8,
                status_code="A",
                status_label="Open",
                headline=None,
                facility_carried="US 41",
                feature_crossed="Canal",
                adt=18000,
                adt_suspect=False,
                year_built=1962,
                why=None,
            ),
            8.0,
        ),
    ]
    monkeypatch.setattr(Config, "ROUTE_LIST_CAP", 1)
    payload = _client(
        monkeypatch,
        matches=matches,
        route={
            "geometry": {
                "type": "LineString",
                "coordinates": [[-87.63, 41.88], [-87.68, 42.05]],
            },
            "distance_m": 22116.6,
            "duration_s": 1574.1,
            "steps": [],
            "roads": ["Interstate 90", "US 41"],
        },
    ).get(
        "/api/drive?from=-87.63,41.88&to=-87.68,42.05"
    ).get_json()
    assert payload["summary"]["bridges"] == 2
    assert payload["summary"]["poor"] == 1
    assert payload["summary"]["good"] == 1
    assert payload["summary"]["listed"] == 2
    assert payload["summary"]["capped"] is True
    assert [item["id"] for item in payload["bridges"]] == ["17-POOR", "17-GOOD"]
    assert payload["bridges"][0]["condition"] == "P"
    assert payload["bridges"][0]["score"] == 40
    assert payload["bridges"][0]["adt"] == 18000
    assert payload["worst"][0]["id"] == "17-POOR"
    assert payload["route"]["steps"] == []


def _api_bridge(**kw):
    defaults = dict(
        id=1,
        state_code="48",
        structure_number="X",
        lat=29.76,
        lng=-95.37,
        bridge_condition="G",
        lowest_rating=7,
        unease_score=10,
        along=0.4,
        status_code="A",
        status_label="Open",
        headline=None,
        facility_carried="MAIN ST",
        feature_crossed="BUFFALO BAYOU",
        adt=8000,
        adt_suspect=False,
        year_built=1980,
        why=None,
    )
    defaults.update(kw)
    return SimpleNamespace(**defaults)


def test_drive_api_keeps_on_route_spans_not_overpasses(monkeypatch):
    matches = [
        (
            _api_bridge(
                id=1,
                structure_number="UNDER",
                facility_carried="INTERSTATE 45",
                feature_crossed="MAIN ST",
                bridge_condition="P",
                unease_score=50,
            ),
            12.0,
        ),
        (
            _api_bridge(
                id=2,
                structure_number="ON",
                facility_carried="W ALABAMA ST",
                feature_crossed="BUFFALO BAYOU",
                bridge_condition="F",
                unease_score=30,
            ),
            8.0,
        ),
    ]
    route = {
        "geometry": {
            "type": "LineString",
            "coordinates": [[-95.38, 29.75], [-95.36, 29.77]],
        },
        "distance_m": 1200,
        "duration_s": 90,
        "steps": [],
        "roads": ["West Alabama Street", "Main Street"],
    }
    payload = _client(monkeypatch, route=route, matches=matches).get(
        "/api/drive?from=-95.38,29.75&to=-95.36,29.77"
    ).get_json()
    assert [item["id"] for item in payload["bridges"]] == ["48-ON"]
    assert payload["summary"]["bridges"] == 1
    assert payload["summary"]["poor"] == 0
    assert payload["worst"][0]["id"] == "48-ON"


def test_drive_api_nameless_osrm_drops_the_overpass(monkeypatch):
    matches = [
        (
            _api_bridge(
                id=1,
                structure_number="I90",
                facility_carried="INTERSTATE 90",
                feature_crossed="MAIN ST",
                bridge_condition="P",
                unease_score=50,
            ),
            4.0,
        ),
        (
            _api_bridge(
                id=2,
                structure_number="MAIN",
                facility_carried="MAIN STREET",
                feature_crossed="CHICAGO RIVER",
                bridge_condition="G",
                unease_score=8,
            ),
            6.0,
        ),
    ]
    route = {
        "geometry": {
            "type": "LineString",
            "coordinates": [[-87.63, 41.88], [-87.62, 41.89]],
        },
        "distance_m": 400,
        "duration_s": 40,
        "steps": [],
        "roads": [],
    }
    payload = _client(monkeypatch, route=route, matches=matches).get(
        "/api/drive?from=-87.63,41.88&to=-87.62,41.89"
    ).get_json()
    assert payload["bridges"] == []
    assert payload["worst"] == []
    assert payload["summary"]["bridges"] == 0
    assert all("I90" not in item["id"] for item in payload["bridges"])


def test_drive_maps_router_errors(monkeypatch):
    from backend.route import RouteError

    missing = _client(
        monkeypatch, error=RouteError("no driving route for these points", status=404)
    ).get("/api/drive?from=-87.63,41.88&to=-87.68,42.05")
    assert missing.status_code == 404
    assert missing.get_json()["error"] == "no driving route for these points"

    down = _client(
        monkeypatch, error=RouteError("routing unavailable", status=502)
    ).get("/api/drive?from=-87.63,41.88&to=-87.68,42.05")
    assert down.status_code == 502
    assert down.get_json()["error"] == "routing unavailable"
