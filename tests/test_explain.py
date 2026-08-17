from datetime import date

from backend.explain import (
    METHODOLOGY,
    load_ratings_paragraph,
    rating_plain,
    scour_plain,
    status_plain,
    structure_intro,
)
from backend.scoring import derive

TODAY = date(2026, 8, 16)

SEAWOLF = {
    "deck": "6",
    "superstructure": "4",
    "substructure": "5",
    "culvert": "N",
    "lowest_rating": 4,
    "bridge_condition": "P",
    "status_code": "P",
    "scour": "3",
    "fracture": "Y",
    "year_built": 1960,
    "adt": 9100,
    "inspect_raw": "122",
    "inspect_freq_months": 24,
    "functional_class": "14",
    "facility_carried": "SEAWOLF PARKWAY",
    "material_code": "3",
    "design_code": "02",
}

FORBIDDEN_CLAIMS = (
    "safe to drive",
    "safety score",
    "about to fall",
    "likely to collapse",
    "inspectors found a crack",
    "inspectors found a fracture",
)


def test_rating_copy_covers_the_scale():
    assert "No notable problems" in rating_plain(9)
    assert "minor defects" in rating_plain(8)
    assert "Good condition range" in rating_plain(7)
    assert "Fair and Poor" in rating_plain(6)
    assert "structurally serviceable" in rating_plain(5)
    assert "advanced deterioration" in rating_plain(4)
    assert "does not by itself mean the bridge is unsafe" in rating_plain(4)
    assert "serious deterioration" in rating_plain(3)
    assert "not a prediction that the structure will fail" in rating_plain(3)
    assert "closely monitored" in rating_plain(2)
    assert "imminent failure" in rating_plain(1)
    assert "out of service" in rating_plain(0)


def test_status_copy_does_not_infer_a_reason_for_closure():
    assert "heavier vehicle loads are restricted" in status_plain("P")
    assert "does not show that posting as already in place" in status_plain("B")
    assert "Temporary structural support" in status_plain("D")
    assert "does not by itself say why" in status_plain("K")


def test_scour_copy_keeps_codes_distinct():
    assert "not scour-critical" in scour_plain("4")
    assert "not scour-critical" in scour_plain("U")
    assert "not completed" in scour_plain("6")
    assert "scour-critical" in scour_plain("3")
    assert "scour-critical" in scour_plain("2")
    assert "failed from scour" in scour_plain("0")
    assert "erosion of soil" in scour_plain("3")


def test_nstm_is_a_characteristic_not_damage():
    derived = derive({**SEAWOLF, "status_code": "A", "scour": "N", "inspect_raw": "924"}, today=TODAY)
    redun = next(row for row in derived["explanations"] if row["key"] == "redundancy")
    assert redun["title"] == "Limited structural redundancy"
    assert "does not mean inspectors found a crack" in redun["plain"]
    assert "NSTM" in redun["technical"]
    assert "fracture-critical" in redun["technical"]
    blob = redun["plain"].lower()
    assert "inspectors found a crack" not in blob.replace("does not mean inspectors found a crack", "")


def test_seawolf_summary_is_human():
    derived = derive(SEAWOLF, today=TODAY)
    text = " ".join(derived["summary_paragraphs"])
    assert "support structure is rated 4/9" in text
    assert "Poor condition category" in text
    assert "load restricted" in text
    assert "vulnerable to scour" in text
    assert "limited structural redundancy" in text
    assert "9,100 vehicles" in text
    assert " · " not in text
    for phrase in FORBIDDEN_CLAIMS:
        assert phrase not in text.lower()
    assert METHODOLOGY in derived["methodology"]
    assert "not an FHWA grade" in derived["methodology"]


def test_scour_four_is_not_called_critical():
    derived = derive(
        {**SEAWOLF, "scour": "4", "fracture": "N", "status_code": "A", "inspect_raw": "924"},
        today=TODAY,
    )
    scour = next(row for row in derived["explanations"] if row["key"] == "scour")
    assert "scour-critical" not in scour["title"].lower()
    assert "not scour-critical" in scour["plain"]


def test_unknown_scour_is_not_called_critical():
    derived = derive(
        {**SEAWOLF, "scour": "U", "fracture": "N", "status_code": "A", "inspect_raw": "924"},
        today=TODAY,
    )
    scour = next(row for row in derived["explanations"] if row["key"] == "scour")
    assert "unknown" in scour["title"].lower()
    assert "not scour-critical" in scour["plain"]


def test_traffic_copy_separates_exposure_from_condition():
    derived = derive(SEAWOLF, today=TODAY)
    traffic = next(row for row in derived["explanations"] if row["key"] == "traffic")
    assert "does not change the inspector's condition rating" in traffic["plain"]


def test_structure_intro_and_load_copy_stay_dry():
    assert "steel movable" in structure_intro("steel movable — bascule", "Local Toll Authority")
    paragraph = load_ratings_paragraph("3.5 tons", "2.9 tons", 3.5, posted=True)
    assert "3.5 tons" in paragraph
    assert "2.9 tons" in paragraph
    assert "safe" not in paragraph.lower()
    assert "load posting" in paragraph
