from backend.api import _radius_meters
from backend.ingest import (
    NBI_STATE_CODES,
    build_queries,
    page_is_complete,
    remaining_queries,
)


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
