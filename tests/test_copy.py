from pathlib import Path

from backend.lookups import band_label, condition_word

ROOT = Path(__file__).resolve().parents[1]

FORBIDDEN = (
    "Looks fine",
    "Worth a look",
    "Serious shape",
    "Bad shape",
    "Yours first",
    "about to fall",
    "Run the ingest",
    "Nothing to flag",
    "gets honest",
)

SCAN = [
    ROOT / "frontend" / "index.html",
    ROOT / "frontend" / "src" / "format.js",
    ROOT / "frontend" / "src" / "App.jsx",
    ROOT / "frontend" / "src" / "Detail.jsx",
    ROOT / "backend" / "api.py",
]


def test_unknown_condition_is_not_good():
    assert band_label(None) == "Unknown"
    assert band_label("") == "Unknown"
    assert band_label("X") == "Unknown"
    assert condition_word(None) is None
    assert condition_word(7) == "Good"
    assert condition_word(4) == "Poor"


def test_user_facing_copy_is_dry():
    blob = "\n".join(path.read_text() for path in SCAN)
    for phrase in FORBIDDEN:
        assert phrase not in blob, phrase
    assert "★" not in (ROOT / "frontend" / "src" / "Detail.jsx").read_text()


def test_zoom_hint_matches_across_api_and_ui():
    api = (ROOT / "backend" / "api.py").read_text()
    fmt = (ROOT / "frontend" / "src" / "format.js").read_text()
    assert "Zoom in to city scale to see structures." in api
    assert "Zoom in to city scale to see structures." in fmt


def test_css_official_dots_use_original_good_fair():
    css = (ROOT / "frontend" / "src" / "index.css").read_text()
    assert "--good: #5c7a52" in css
    assert "--fair: #c4a84a" in css
    assert "--poor: #b42318" in css
    assert ".rating.is-poor" in css
    assert ".rating.is-low" not in css


def test_overlays_use_hairlines_not_drop_shadows():
    css = (ROOT / "frontend" / "src" / "index.css").read_text()
    assert ".search-hits" in css
    assert ".map-popup" in css
    assert "box-shadow: 0 6px 24px" not in css
    assert "box-shadow: 0 8px 24px" not in css
    assert "max-width: 360px" not in css
    assert "max-width: 480px" in css
