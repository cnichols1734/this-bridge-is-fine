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
    ROOT / "frontend" / "src" / "TripBar.jsx",
    ROOT / "frontend" / "src" / "NavOverlay.jsx",
    ROOT / "backend" / "api.py",
    ROOT / "backend" / "route.py",
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


def test_low_zoom_does_not_claim_city_scale_is_required():
    api = (ROOT / "backend" / "api.py").read_text()
    fmt = (ROOT / "frontend" / "src" / "format.js").read_text()
    lie = "Zoom in to city scale to see structures."
    assert lie not in api
    assert lie not in fmt
    assert "No structures in this view." in fmt


def test_drive_map_uses_route_bridges_not_viewport():
    app = (ROOT / "frontend" / "src" / "App.jsx").read_text()
    fmt = (ROOT / "frontend" / "src" / "format.js").read_text()
    assert "mapDotsCollection" in app
    assert "geojson={mapGeojson}" in app
    assert "if (drivePinsOn.current) return" in app
    assert "driveBridgesForMap" in fmt
    assert "driveBridgesGeojson" in fmt


def test_trip_errors_are_not_desktop_only():
    app = (ROOT / "frontend" / "src" / "App.jsx").read_text()
    bar = (ROOT / "frontend" / "src" / "TripBar.jsx").read_text()
    assert "error={tripError}" in app
    assert "tripOpen && (tripError || tripBusy || fixingStart)" in app
    assert "trip-error" in bar
    assert "Daily crossings on Poor" not in bar


def test_css_official_dots_use_original_good_fair():
    css = (ROOT / "frontend" / "src" / "index.css").read_text()
    assert "--good: #5c7a52" in css
    assert "--fair: #c4a84a" in css
    assert "--poor: #b42318" in css
    assert ".rating.is-poor" in css
    assert ".rating.is-low" not in css


def test_landscape_peek_keeps_trip_facts_visible():
    css = (ROOT / "frontend" / "src" / "index.css").read_text()
    sheet = (ROOT / "frontend" / "src" / "sheetDetents.js").read_text()
    assert ".sheet-pulse:not(.trip-pulse) .pulse-copy" in css
    assert ".sheet .trip-pulse .pulse-copy" in css
    assert ".trip-worst" in css
    assert ".sheet.peek .trip-worst" not in css
    assert ".sheet.peek .sheet-body" in css
    assert "overflow: visible" in css
    assert "Math.max(292" in sheet


def test_nav_chrome_has_a_labeled_exit():
    nav = (ROOT / "frontend" / "src" / "NavOverlay.jsx").read_text()
    app = (ROOT / "frontend" / "src" / "App.jsx").read_text()
    css = (ROOT / "frontend" / "src" / "index.css").read_text()
    assert "nav-exit" in nav
    assert "driveBack" in nav
    assert "onExit={clearTrip}" in app
    assert ".nav-exit" in css


def test_preview_list_matches_route_pins():
    app = (ROOT / "frontend" / "src" / "App.jsx").read_text()
    assert "const routeOnMap = Boolean(tripPayload?.route)" in app
    assert "routeOnMap ? tripPayload.bridges" in app
    assert "{routeOnMap ? COPY.driveBridges : COPY.nearest}" in app


def test_follow_camera_is_snappy():
    view = (ROOT / "frontend" / "src" / "MapView.jsx").read_text()
    assert "duration: 260" in view
    assert "duration: 900" not in view


def test_drive_start_waits_for_a_fresh_precise_fix():
    geo = (ROOT / "frontend" / "src" / "geo.js").read_text()
    app = (ROOT / "frontend" / "src" / "App.jsx").read_text()
    fmt = (ROOT / "frontend" / "src" / "format.js").read_text()
    assert "maximumAge: 0" in geo
    assert "maximumAge: 4000" not in geo
    assert "waitForPreciseFix" in geo
    assert "waitForPreciseFix" in app
    open_drive = app.split("const openDrive")[1].split("const confirmTrip")[0]
    assert "waitForPreciseFix" in open_drive
    assert "setTripStart(null)" in open_drive
    assert "userLocation" not in open_drive
    assert "Location is approximate. Using the map center." in fmt
    assert "Finding your location." in fmt


def test_map_has_an_always_visible_locate_control():
    app = (ROOT / "frontend" / "src" / "App.jsx").read_text()
    nav = (ROOT / "frontend" / "src" / "NavOverlay.jsx").read_text()
    css = (ROOT / "frontend" / "src" / "index.css").read_text()
    fmt = (ROOT / "frontend" / "src" / "format.js").read_text()
    assert "LocateButton" in nav
    assert "LocateButton" in app
    assert 'className="recenter"' in app
    assert "away && userLocation" not in app
    assert "locate()" in app
    assert "refreshPrecise(true)" in app
    assert "My location" in fmt
    assert ".locate-btn" in css
    assert "color: #0071e3" not in css.split(".locate-btn")[1][:400]


def test_drive_is_a_real_button():
    app = (ROOT / "frontend" / "src" / "App.jsx").read_text()
    css = (ROOT / "frontend" / "src" / "index.css").read_text()
    assert "DriveButton" in app
    assert "Start a drive" in (ROOT / "frontend" / "src" / "format.js").read_text()
    assert ".drive-btn" in css
    assert "background: var(--ink)" in css


def test_overlays_use_hairlines_not_drop_shadows():
    css = (ROOT / "frontend" / "src" / "index.css").read_text()
    assert ".search-hits" in css
    assert ".map-popup" in css
    assert "box-shadow: 0 6px 24px" not in css
    assert "box-shadow: 0 8px 24px" not in css
    assert "max-width: 360px" not in css
    assert "max-width: 480px" in css
