from backend.api import _radius_meters
from backend.ingest import page_is_complete


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
