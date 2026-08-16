from datetime import date

from backend.scoring import derive, parse_inspect_date, publicize_text, unease_score


def test_inspect_dates():
    assert parse_inspect_date("424") == date(2024, 4, 1)
    assert parse_inspect_date("1223") == date(2023, 12, 1)
    assert parse_inspect_date("823") == date(2023, 8, 1)


def test_i110_is_sticky():
    derived = derive(
        {
            "deck": "4",
            "superstructure": "4",
            "substructure": "7",
            "culvert": "N",
            "lowest_rating": 4,
            "bridge_condition": "P",
            "status_code": "A",
            "scour": "N",
            "fracture": "N",
            "year_built": 1996,
            "adt": 300000,
            "inspect_raw": "823",
            "inspect_freq_months": 24,
            "functional_class": "11",
            "facility_carried": "INTERSTATE 110",
            "material_code": "5",
            "design_code": "02",
        },
        today=date(2026, 8, 15),
    )
    assert derived["adt_suspect"] is False
    assert derived["worst_component"] in {"deck", "superstructure"}
    assert derived["unease_score"] >= 60
    assert "300,000" in derived["headline"]
    assert "Poor" in derived["headline"]
    assert "Road surface" in derived["headline"] or "Support" in derived["headline"]
    assert "Deck:" not in derived["headline"]
    assert "Superstructure" not in derived["headline"]


def test_publicize_rewrites_stored_jargon():
    assert (
        publicize_text("Deck: Poor. Superstructure: Fair.")
        == "Road surface: Poor. Support: Fair."
    )


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


def test_busy_sound_bridge_stays_sound():
    """Traffic alone must not push a well-rated bridge down the list."""
    quiet = unease_score(
        lowest=7,
        adt_capped=400,
        status="A",
        scour="N",
        fracture="N",
        overdue=False,
        year_built=2012,
        culvert=False,
    )
    busy = unease_score(
        lowest=7,
        adt_capped=250_000,
        status="A",
        scour="N",
        fracture="N",
        overdue=False,
        year_built=2012,
        culvert=False,
    )
    assert busy - quiet < 8
    assert busy < 25


def test_bad_urban_bridges_stay_distinguishable():
    """A hard clamp used to collapse every bad city bridge onto one value."""
    def score(lowest, **kw):
        return unease_score(
            lowest=lowest,
            adt_capped=102_000,
            status=kw.get("status", "A"),
            scour=kw.get("scour", "N"),
            fracture=kw.get("fracture", "N"),
            overdue=kw.get("overdue", False),
            year_built=kw.get("year_built", 1937),
            culvert=False,
        )

    poor = score(4)
    serious = score(3)
    critical = score(2)
    posted_and_scoured = score(3, status="P", scour="3")
    closed_failure = score(0, status="K", scour="3", fracture="Y")

    ordered = [poor, serious, critical, posted_and_scoured, closed_failure]
    assert poor < serious < critical
    assert serious < posted_and_scoured < closed_failure
    assert len(set(ordered)) == len(ordered)
    assert max(ordered) < 100


def test_culvert_is_downranked():
    rural = unease_score(
        lowest=3,
        adt_capped=40,
        status="A",
        scour="N",
        fracture="N",
        overdue=False,
        year_built=1920,
        culvert=True,
    )
    interstate = unease_score(
        lowest=4,
        adt_capped=300000,
        status="A",
        scour="N",
        fracture="N",
        overdue=False,
        year_built=1996,
        culvert=False,
    )
    assert interstate > rural
