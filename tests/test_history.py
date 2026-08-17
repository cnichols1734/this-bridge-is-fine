from backend.file_payload import file_blocks
from backend.history import (
    condition_trend,
    history_row,
    parse_history_record,
    parse_history_text,
    pick_delimited_zip,
)
from backend.lookups import format_length_m, format_tons, short_tons


def test_history_row_computes_lowest():
    row = history_row(
        state_code="17",
        structure_number="016603000000000",
        nbi_year="2022",
        deck="6",
        superstructure="4",
        substructure="5",
        culvert="N",
    )
    assert row["lowest_rating"] == 4
    assert row["nbi_year"] == "2022"


def test_parse_history_text_skips_junk():
    blob = (
        "STATE_CODE_001,STRUCTURE_NUMBER_008,DECK_COND_058,"
        "SUPERSTRUCTURE_COND_059,SUBSTRUCTURE_COND_060,CULVERT_COND_062,LOWEST_RATING\n"
        "17,016603000000000,6,4,5,N,4\n"
        ",,,,,,\n"
    )
    rows = parse_history_text(blob, "2021")
    assert len(rows) == 1
    assert rows[0]["state_code"] == "17"
    assert rows[0]["lowest_rating"] == 4


def test_parse_history_record_uses_year_hint():
    row = parse_history_record(
        {
            "STATE_CODE_001": "06",
            "STRUCTURE_NUMBER_008": "39C0347",
            "DECK_COND_058": "3",
            "SUPERSTRUCTURE_COND_059": "3",
            "SUBSTRUCTURE_COND_060": "0",
            "CULVERT_COND_062": "N",
        },
        "2020",
    )
    assert row["nbi_year"] == "2020"
    assert row["lowest_rating"] == 0


def test_condition_trend_stable_and_decline():
    stable = condition_trend(
        [
            {"nbi_year": "2020", "lowest_rating": 5},
            {"nbi_year": "2021", "lowest_rating": 5},
            {"nbi_year": "2022", "lowest_rating": 6},
            {"nbi_year": "2023", "lowest_rating": 5},
            {"nbi_year": "2024", "lowest_rating": 5},
        ]
    )
    assert stable is not None
    assert len(stable["points"]) == 5
    assert "stable" in stable["insight"]

    declined = condition_trend(
        [
            {"nbi_year": "2020", "lowest_rating": 7},
            {"nbi_year": "2024", "lowest_rating": 4},
        ]
    )
    assert "declined" in declined["insight"]
    assert condition_trend([{"nbi_year": "2024", "lowest_rating": 5}]) is None


def test_pick_delimited_zip_prefers_comma_file():
    html = """
    <a href="/bridge/nbi/2024all.zip">No delimiter</a>
    <a href="/bridge/nbi/2024del.zip">Delimited Files single file</a>
    <a href="/bridge/nbi/element2024.zip">elements</a>
    """
    assert pick_delimited_zip(html, "https://www.fhwa.dot.gov/bridge/nbi/ascii2024.cfm").endswith(
        "2024del.zip"
    )


def test_pick_delimited_zip_uses_heading_context():
    html = """
    <h3>No Delimiter</h3>
    <a href="https://www.fhwa.dot.gov/bridge/nbi/2024all.zip">single file</a>
    <h3>Delimited Files</h3>
    <p>Comma Delimited</p>
    <a href="https://www.fhwa.dot.gov/bridge/nbi/2024comma.zip">
    Download Highway Bridges for all States (in a single file) as a zip file
    </a>
    """
    assert pick_delimited_zip(html, "https://www.fhwa.dot.gov/bridge/nbi/ascii2024.cfm").endswith(
        "2024comma.zip"
    )


def test_file_blocks_and_units():
    class Bridge:
        structure_type = "steel movable — bascule"
        material_code = "3"
        design_code = "16"
        owner_code = "32"
        maintenance_code = "32"
        year_built = 1965
        year_reconstructed = 1969
        structure_length_m = 3879.2
        max_span_m = 5.5
        deck_width_m = 0.9
        deck_area_m2 = 34600
        route_prefix = "4"
        route_number = "0"
        lanes_on = 2
        lanes_under = None
        toll_code = "1"
        history_code = "2"
        scour = "U"
        detour_km = 113
        operating_rating = 3.2
        inventory_rating = 2.6
        status_code = "P"

    blocks = file_blocks(Bridge(), [])
    assert blocks["structure"]["owner"] == "Local Toll Authority"
    assert "12,727 ft" in blocks["dimensions"]["length_label"]
    assert blocks["classification"]["route_type"] == "County road"
    assert blocks["load_ratings"]["operating_label"]
    assert "safe" not in (blocks["load_ratings"]["paragraph"] or "").lower()
    assert format_tons(3.2) == "3.5 tons"
    assert short_tons(3.2) == 3.5
    assert format_length_m(5.5).startswith("18.0 ft")
