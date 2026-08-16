from backend.api import _radius_meters, create_app
from backend.ingest import (
    NBI_STATE_CODES,
    build_queries,
    map_feature,
    page_is_complete,
    remaining_queries,
    state_code_from_query,
    valid_point,
    work_items,
)


def test_ingest_status_route_is_registered():
    rules = {rule.rule for rule in create_app().url_map.iter_rules()}
    assert "/api/ingest" in rules
    assert "/api/meta" in rules


def test_worst_radius_is_kilometers_not_megameters():
    assert _radius_meters(25, 1.0, 80) == 25_000
    assert _radius_meters(0.2, 1.0, 80) == 1_000
    assert _radius_meters(12, 0.5, 80) == 12_000


def test_empty_page_is_not_done_before_count():
    assert page_is_complete(0, False, 352000, 624193) is False


def test_empty_page_is_done_at_count():
    assert page_is_complete(0, False, 624193, 624193) is True


def test_short_page_without_exceeded_is_done():
    assert page_is_complete(500, False, 620000, 620500) is True


def test_full_page_keeps_going():
    assert page_is_complete(2000, True, 350000, 624193) is False


def test_national_queries_walk_each_state_then_leftovers():
    queries = build_queries()
    assert queries[0] == "STATE_CODE_001='01'"
    assert queries[4] == "STATE_CODE_001='06'"
    assert queries[-2] == f"STATE_CODE_001='{NBI_STATE_CODES[-1]}'"
    assert queries[-1].startswith("STATE_CODE_001 IS NULL OR STATE_CODE_001 NOT IN")
    assert len(queries) == len(NBI_STATE_CODES) + 1


def test_state_filter_is_a_single_query():
    assert build_queries(state="6") == ["STATE_CODE_001='06'"]


def test_resume_skips_finished_states():
    queries = [
        "STATE_CODE_001='01'",
        "STATE_CODE_001='02'",
        "STATE_CODE_001='04'",
        "STATE_CODE_001='05'",
        "STATE_CODE_001='06'",
    ]
    assert remaining_queries(queries, "STATE_CODE_001='05'") == ["STATE_CODE_001='06'"]


def test_resume_without_checkpoint_starts_over():
    queries = ["STATE_CODE_001='01'", "STATE_CODE_001='02'"]
    assert remaining_queries(queries, None) == queries
    assert remaining_queries(queries, "STATE_CODE_001='99'") == queries


def test_resume_after_last_state_is_empty():
    queries = ["STATE_CODE_001='01'", "STATE_CODE_001='02'"]
    assert remaining_queries(queries, "STATE_CODE_001='02'") == []


def test_mid_state_resume_keeps_offset():
    queries = [
        "STATE_CODE_001='05'",
        "STATE_CODE_001='06'",
        "STATE_CODE_001='08'",
    ]
    # Arkansas finished; California killed at offset 12000.
    work = work_items(queries, "STATE_CODE_001='05'", 12000)
    assert work == [
        ("STATE_CODE_001='06'", 12000),
        ("STATE_CODE_001='08'", 0),
    ]


def test_resume_after_finished_state_starts_next_at_zero():
    queries = ["STATE_CODE_001='01'", "STATE_CODE_001='02'"]
    assert work_items(queries, "STATE_CODE_001='01'", 0) == [
        ("STATE_CODE_001='02'", 0)
    ]


def test_state_code_from_plain_query():
    assert state_code_from_query("STATE_CODE_001='48'") == "48"
    assert state_code_from_query("STATE_CODE_001 IS NULL OR STATE_CODE_001 NOT IN ('01')") is None


def test_valid_point_keeps_territories_and_drops_junk():
    assert valid_point(0, 0) is False
    assert valid_point(41.88, -87.62) is True
    assert valid_point(21.3, -157.85) is True  # Honolulu
    assert valid_point(18.45, -66.07) is True  # San Juan
    assert valid_point(13.44, 144.79) is True  # Guam
    assert valid_point(-14.28, -170.70) is True  # American Samoa
    assert valid_point(13.44, 0) is False
    assert valid_point(80.0, -90.0) is False


def test_map_feature_is_idempotent():
    attrs = {
        "STATE_CODE_001": "17",
        "STRUCTURE_NUMBER_008": "016603000000000",
        "DATE": "2025",
        "LATDD": 41.888525,
        "LONGDD": -87.614167,
        "FACILITY_CARRIED_007": "LAKE SHORE DRIVE",
        "FEATURES_DESC_006A": "MAIN BR CHICAGO RIV",
        "LOCATION_009": "402 N & 520 E",
        "DECK_COND_058": "6",
        "SUPERSTRUCTURE_COND_059": "4",
        "SUBSTRUCTURE_COND_060": "5",
        "CULVERT_COND_062": "N",
        "LOWEST_RATING": 4,
        "BRIDGE_CONDITION": "P",
        "OPEN_CLOSED_POSTED_041": "P",
        "SCOUR_CRITICAL_113": "N",
        "FRACTURE_092A": "Y",
        "YEAR_BUILT_027": 1937,
        "YEAR_RECONSTRUCTED_106": 1988,
        "ADT_029": 102000,
        "YEAR_ADT_030": 2022,
        "DATE_OF_INSPECT_090": "924",
        "INSPECT_FREQ_MONTHS_091": 24,
        "FUNCTIONAL_CLASS_026": "14",
        "STRUCTURE_KIND_043A": "3",
        "STRUCTURE_TYPE_043B": "16",
    }
    first = map_feature(attrs)
    second = map_feature(attrs)
    assert first is not None
    assert first == second
    assert first["state_code"] == "17"
    assert first["bridge_condition"] == "P"
    assert first["unease_score"] == second["unease_score"]
    assert 30 <= first["unease_score"] <= 50
    assert map_feature({**attrs, "LATDD": 0, "LONGDD": 0}) is None
