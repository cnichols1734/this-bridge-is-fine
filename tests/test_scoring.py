from datetime import date

from backend.lookups import is_scour_critical, official_condition_band
from backend.scoring import (
    add_months,
    derive,
    inspect_overdue,
    parse_inspect_date,
    publicize_text,
    score_breakdown,
    unease_score,
)

TODAY = date(2026, 8, 16)


def _base(**kw):
    row = {
        "deck": "7",
        "superstructure": "7",
        "substructure": "7",
        "culvert": "N",
        "lowest_rating": 7,
        "bridge_condition": "G",
        "status_code": "A",
        "scour": "N",
        "fracture": "N",
        "year_built": 2012,
        "adt": 400,
        "inspect_raw": "924",
        "inspect_freq_months": 24,
        "functional_class": "09",
        "facility_carried": "MAIN ST",
        "material_code": "3",
        "design_code": "02",
    }
    row.update(kw)
    return row


def _score(**kw):
    return unease_score(
        lowest=kw.get("lowest", 7),
        adt_capped=kw.get("adt_capped", 400),
        status=kw.get("status", "A"),
        scour=kw.get("scour", "N"),
        fracture=kw.get("fracture", "N"),
        overdue=kw.get("overdue", False),
        year_built=kw.get("year_built", 2012),
        culvert=kw.get("culvert", False),
        adt_suspect=kw.get("adt_suspect", False),
    )


SEAWOLF = _base(
    deck="6",
    superstructure="4",
    substructure="5",
    culvert="N",
    lowest_rating=4,
    bridge_condition="P",
    status_code="P",
    scour="3",
    fracture="Y",
    year_built=1960,
    adt=9100,
    inspect_raw="122",
    inspect_freq_months=24,
    functional_class="14",
    facility_carried="SEAWOLF PARKWAY",
    material_code="3",
    design_code="02",
)


def test_inspect_dates():
    assert parse_inspect_date("424") == date(2024, 4, 1)
    assert parse_inspect_date("1223") == date(2023, 12, 1)
    assert parse_inspect_date("823") == date(2023, 8, 1)


def test_add_months_includes_december():
    assert add_months(date(2023, 12, 1), 24) == date(2025, 12, 1)
    assert add_months(date(2024, 1, 1), 24) == date(2026, 1, 1)


def test_inspect_overdue_has_no_grace_period():
    inspected = date(2024, 4, 1)
    assert inspect_overdue(inspected, 24, date(2026, 3, 31)) is False
    assert inspect_overdue(inspected, 24, date(2026, 4, 1)) is True
    assert inspect_overdue(inspected, 24, date(2026, 6, 1)) is True


def test_publicize_rewrites_stored_jargon():
    assert (
        publicize_text("Deck: Poor. Superstructure: Fair.")
        == "Road surface: Poor. Support structure: Fair."
    )


def test_i110_is_sticky():
    derived = derive(
        _base(
            deck="4",
            superstructure="4",
            substructure="7",
            lowest_rating=4,
            bridge_condition="P",
            year_built=1996,
            adt=300000,
            inspect_raw="823",
            functional_class="11",
            facility_carried="INTERSTATE 110",
            material_code="5",
        ),
        today=TODAY,
    )
    assert derived["adt_suspect"] is False
    assert derived["worst_component"] in {"deck", "superstructure"}
    assert derived["bridge_condition"] == "P"
    assert 45 <= derived["score"] <= 55
    assert "300,000" in derived["headline"]
    assert "Poor" in derived["headline"]
    assert "Road surface" in derived["headline"] or "Support" in derived["headline"]
    assert "Deck:" not in derived["headline"]
    assert "Superstructure" not in derived["headline"]


def test_junk_adt_is_suspect():
    derived = derive(
        {
            "lowest_rating": 3,
            "bridge_condition": "P",
            "status_code": "P",
            "year_built": 1930,
            "adt": 600500,
            "functional_class": "09",
            "facility_carried": "MON CO RT 19/25",
            "design_code": "02",
            "material_code": "3",
        }
    )
    assert derived["adt_suspect"] is True
    assert derived["adt_capped"] == 350000
    assert derived["score_breakdown"]["traffic_deduction"] == 0


def test_excellent_quiet_bridge():
    derived = derive(_base(lowest_rating=9, deck="9", superstructure="9", substructure="9"), today=TODAY)
    assert derived["score"] >= 95
    assert derived["score_band"] == "Few concerns"
    assert derived["bridge_condition"] == "G"


def test_excellent_high_traffic_bridge():
    quiet = _score(lowest=9, adt_capped=400)
    busy = _score(lowest=9, adt_capped=200_000)
    assert quiet == busy
    assert busy >= 95


def test_good_extremely_busy_interstate():
    derived = derive(
        _base(
            lowest_rating=7,
            adt=250000,
            functional_class="11",
            facility_carried="INTERSTATE 90",
        ),
        today=TODAY,
    )
    assert derived["bridge_condition"] == "G"
    assert derived["score"] >= 80
    assert derived["score_breakdown"]["traffic_deduction"] <= 2


def test_busy_sound_bridge_stays_sound():
    quiet = _score(lowest=7, adt_capped=400)
    busy = _score(lowest=7, adt_capped=250_000)
    assert busy - quiet <= 0
    assert abs(quiet - busy) < 8
    assert busy >= 80


def test_fair_bridge():
    derived = derive(_base(lowest_rating=5, deck="5", superstructure="6", substructure="6", bridge_condition="F"), today=TODAY)
    assert derived["bridge_condition"] == "F"
    assert 60 <= derived["score"] <= 70
    assert derived["score_band"] == "Moderate concerns"


def test_plain_poor_four():
    derived = derive(
        _base(lowest_rating=4, deck="6", superstructure="4", substructure="6", bridge_condition="P", adt=0),
        today=TODAY,
    )
    assert derived["bridge_condition"] == "P"
    assert derived["score"] == 54
    assert derived["score"] != 0
    assert derived["score_band"] == "Elevated concerns"


def test_poor_low_traffic_and_high_traffic():
    low = _score(lowest=4, adt_capped=40)
    high = _score(lowest=4, adt_capped=100_000)
    assert 50 <= low <= 54
    assert 48 <= high <= 52
    assert high < low
    assert low - high <= 5


def test_load_restriction_nstm_and_scour_each_deduct():
    plain = _score(lowest=4)
    posted = _score(lowest=4, status="P")
    nstm = _score(lowest=4, fracture="Y")
    scour = _score(lowest=4, scour="3")
    assert plain - posted == 6
    assert plain - nstm == 4
    assert plain - scour == 6


def test_seawolf_combination():
    derived = derive(SEAWOLF, today=TODAY)
    assert derived["bridge_condition"] == "P"
    assert derived["lowest_rating"] == 4
    assert derived["worst_component"] == "superstructure"
    assert 30 <= derived["score"] <= 45
    assert derived["score"] == 34
    parts = derived["score_breakdown"]
    assert parts["condition_base"] == 54
    assert parts["status_deduction"] == 6
    assert parts["scour_deduction"] == 6
    assert parts["redundancy_deduction"] == 4
    assert parts["inspection_deduction"] == 2
    assert parts["traffic_deduction"] == 2
    assert (
        parts["condition_base"]
        - parts["status_deduction"]
        - parts["scour_deduction"]
        - parts["redundancy_deduction"]
        - parts["inspection_deduction"]
        - parts["traffic_deduction"]
        == derived["score"]
    )
    assert derived["score_band"] == "Significant concerns"
    summary = derived["summary"]
    assert "4/9" in summary
    assert "Poor" in summary
    assert "load restricted" in summary
    assert "scour" in summary.lower()
    assert "limited structural redundancy" in summary
    assert "9,100" in summary
    assert "not an official FHWA safety grade" in summary
    assert "fracture-critical" not in summary
    keys = [row["key"] for row in derived["explanations"]]
    assert keys == ["superstructure", "status", "scour", "redundancy", "inspection", "traffic"]


def test_rating_ladder_does_not_collapse():
    def combo(lowest):
        return derive({**SEAWOLF, "superstructure": str(lowest), "lowest_rating": lowest}, today=TODAY)["score"]

    four = combo(4)
    three = combo(3)
    two = combo(2)
    one = combo(1)
    zero = combo(0)
    assert four > three > two
    assert two > one or one == 0
    assert one >= zero
    assert four >= 30
    assert three < 30
    assert zero == 0


def test_serious_critical_imminent_failed():
    assert 35 <= _score(lowest=3) <= 45
    assert 20 <= _score(lowest=2) <= 30
    assert 8 <= _score(lowest=1) <= 12
    assert _score(lowest=0) == 0


def test_scour_codes_are_distinct():
    four = _score(lowest=7, scour="4")
    unknown = _score(lowest=7, scour="U")
    six = _score(lowest=7, scour="6")
    three = _score(lowest=7, scour="3")
    two = _score(lowest=7, scour="2")
    one = _score(lowest=7, scour="1")
    failed = _score(lowest=7, scour="0")
    stable = _score(lowest=7, scour="8")
    assert is_scour_critical("4") is False
    assert is_scour_critical("U") is False
    assert is_scour_critical("3") is True
    assert stable > four
    assert four == unknown
    assert unknown < six or unknown != three
    assert six > three > two > one > failed
    assert stable - four == 3
    assert stable - three == 6
    assert stable - two == 10
    assert stable - one == 16
    assert stable - failed == 20


def test_inspection_timing_only():
    derived = derive(
        _base(inspect_raw="122", inspect_freq_months=24, lowest_rating=7),
        today=TODAY,
    )
    assert derived["inspect_overdue"] is True
    assert derived["inspect_due_on"] == date(2024, 1, 1)
    assert derived["inspect_months_past_due"] == 31
    assert derived["score_breakdown"]["inspection_deduction"] == 2
    assert derived["score"] == 84


def test_age_does_not_change_score():
    old = _score(lowest=7, year_built=1930)
    new = _score(lowest=7, year_built=2018)
    assert old == new


def test_old_good_and_new_poor():
    old_good = derive(_base(year_built=1930, lowest_rating=8, deck="8", superstructure="8", substructure="8"), today=TODAY)
    new_poor = derive(
        _base(year_built=2018, lowest_rating=4, deck="4", superstructure="7", substructure="7", bridge_condition="P"),
        today=TODAY,
    )
    assert old_good["bridge_condition"] == "G"
    assert new_poor["bridge_condition"] == "P"
    assert old_good["score"] > new_poor["score"]
    assert old_good["age_years"] == 96
    assert new_poor["age_years"] == 8


def test_poor_culvert_is_not_boosted():
    rural = _score(lowest=4, adt_capped=0, culvert=True, year_built=1920)
    same = _score(lowest=4, adt_capped=0, culvert=False, year_built=1920)
    derived = derive(
        _base(
            lowest_rating=4,
            bridge_condition="P",
            deck="N",
            superstructure="N",
            substructure="N",
            culvert="4",
            design_code="19",
            material_code="1",
            adt=0,
            year_built=1920,
        ),
        today=TODAY,
    )
    assert rural == same
    assert derived["is_culvert"] is True
    assert derived["bridge_condition"] == "P"
    assert derived["score"] == 54


def test_closed_without_component_failure():
    derived = derive(_base(status_code="K", lowest_rating=7, adt=0), today=TODAY)
    assert derived["score"] == 82
    assert derived["score"] != 0
    assert derived["status_label"] == "Closed"
    assert "closed" in derived["summary"].lower()


def test_missing_ratings_are_not_good():
    derived = derive({"adt": 100, "status_code": "A"}, today=TODAY)
    assert derived["lowest_rating"] is None
    assert derived["bridge_condition"] is None
    assert derived["score"] == 70
    assert derived["score_band"] != "Few concerns"


def test_official_gfp_is_independent_of_score():
    poor_quiet = derive(
        _base(
            lowest_rating=4,
            bridge_condition="P",
            year_built=1980,
            adt=40,
            design_code="19",
            material_code="1",
            deck="N",
            superstructure="N",
            substructure="N",
            culvert="4",
        ),
        today=TODAY,
    )
    good_busy = derive(
        _base(
            lowest_rating=8,
            deck="8",
            superstructure="8",
            substructure="8",
            bridge_condition="G",
            year_built=2018,
            adt=180000,
            functional_class="11",
            facility_carried="INTERSTATE 90",
        ),
        today=TODAY,
    )
    assert poor_quiet["bridge_condition"] == "P"
    assert good_busy["bridge_condition"] == "G"
    assert good_busy["score"] >= 85
    assert poor_quiet["is_culvert"] is True
    assert 50 <= poor_quiet["score"] <= 56


def test_official_band_fills_from_lowest_when_source_missing():
    assert official_condition_band(8, None) == "G"
    assert official_condition_band(6, "") == "F"
    assert official_condition_band(4, None) == "P"
    assert official_condition_band(0, None) == "P"
    assert official_condition_band(None, None) is None
    assert official_condition_band(4, "G") == "G"
    derived = derive({"lowest_rating": 5, "bridge_condition": None, "adt": 100})
    assert derived["bridge_condition"] == "F"


def test_lake_shore_drive_is_poor_but_not_zero():
    derived = derive(
        _base(
            deck="6",
            superstructure="4",
            substructure="5",
            lowest_rating=4,
            bridge_condition="P",
            status_code="P",
            scour="N",
            fracture="Y",
            year_built=1937,
            adt=102000,
            inspect_raw="924",
            inspect_freq_months=24,
            functional_class="14",
            facility_carried="LAKE SHORE DRIVE",
            material_code="3",
            design_code="16",
        ),
        today=TODAY,
    )
    assert derived["bridge_condition"] == "P"
    assert derived["lowest_rating"] == 4
    assert derived["worst_component"] == "superstructure"
    assert 35 <= derived["score"] <= 50
    assert derived["score"] != 0


def test_typical_poor_never_reaches_zero():
    derived = derive(SEAWOLF, today=TODAY)
    piled = _score(
        lowest=4,
        adt_capped=200_000,
        status="D",
        scour="2",
        fracture="Y",
        overdue=True,
    )
    assert derived["score"] > 0
    assert piled >= 12
    assert _score(lowest=4, status="K", scour="3", fracture="Y", overdue=True) > 0


def test_higher_score_is_always_better():
    ordered = [_score(lowest=n) for n in range(10)]
    assert ordered == sorted(ordered)
    assert ordered[0] == 0
    assert ordered[-1] == 98


def test_breakdown_is_inspectable():
    parts = score_breakdown(
        lowest=4,
        adt_capped=9100,
        status="P",
        scour="3",
        fracture="Y",
        overdue=True,
    )
    assert set(parts) >= {
        "condition_base",
        "status_deduction",
        "scour_deduction",
        "redundancy_deduction",
        "inspection_deduction",
        "traffic_deduction",
        "score",
        "score_band",
    }
    assert parts["score"] == 34
