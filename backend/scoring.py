"""Derived fields. This is the product."""

from __future__ import annotations

import math
from datetime import date
from typing import Any

from backend.lookups import (
    band_label,
    condition_word,
    is_culvert,
    is_fracture_critical,
    is_freeway,
    is_scour_critical,
    official_condition_band,
    rating_int,
    status_label,
    structure_phrase,
)

COMPONENT_PUBLIC = {
    "deck": "road surface",
    "superstructure": "support",
    "substructure": "foundation",
    "culvert": "culvert",
}


def public_component(key: str | None, title: bool = False) -> str:
    label = COMPONENT_PUBLIC.get(key or "", key or "")
    return label[:1].upper() + label[1:] if title and label else label


def publicize_text(text: str | None) -> str | None:
    """Rewrite stored NBI jargon for the file the public reads."""
    if not text:
        return text
    pairs = (
        ("Superstructure", "Support"),
        ("superstructure", "support"),
        ("Substructure", "Foundation"),
        ("substructure", "foundation"),
        ("Deck", "Road surface"),
        ("deck", "road surface"),
    )
    out = text
    for old, new in pairs:
        out = out.replace(old, new)
    return out


CONDITION_POINTS = {
    9: 0,
    8: 2,
    7: 5,
    6: 12,
    5: 22,
    4: 45,
    3: 65,
    2: 80,
    1: 92,
    0: 100,
}

STATUS_POINTS = {
    "K": 18,
    "D": 15,
    "P": 12,
    "R": 10,
    "E": 10,
    "B": 8,
}

CURRENT_YEAR = date.today().year
ADT_HARD_CAP = 350_000
ADT_ABSURD = 400_000
ADT_LOCAL_SUSPECT = 150_000


def parse_inspect_date(raw: str | None, today: date | None = None) -> date | None:
    """Item 90 is MMYY or MYY ('424' → 2024-04, '1223' → 2023-12)."""
    today = today or date.today()
    text = "".join(ch for ch in str(raw or "") if ch.isdigit())
    if len(text) not in {3, 4}:
        return None
    if len(text) == 3:
        month, year_two = int(text[0]), int(text[1:])
    else:
        month, year_two = int(text[:2]), int(text[2:])
    if month < 1 or month > 12:
        return None
    century_cutoff = (today.year % 100) + 1
    year = (2000 + year_two) if year_two <= century_cutoff else (1900 + year_two)
    try:
        return date(year, month, 1)
    except ValueError:
        return None


def add_months(start: date, months: int) -> date:
    total = start.year * 12 + (start.month - 1) + months
    year, month0 = divmod(total, 12)
    last_day = date(year, month0 + 1, 1) if month0 < 11 else date(year + 1, 1, 1)
    return last_day


def inspect_overdue(
    inspect_on: date | None, freq_months: int | None, today: date | None = None
) -> bool:
    if not inspect_on or not freq_months or freq_months <= 0:
        return False
    today = today or date.today()
    due = add_months(inspect_on, freq_months + 2)
    return today >= due


def adt_hygiene(
    adt: int | None, functional_class: str | None, facility_carried: str | None
) -> tuple[int, bool]:
    traffic = max(int(adt or 0), 0)
    freeway = is_freeway(functional_class, facility_carried)
    suspect = traffic > ADT_ABSURD or (not freeway and traffic > ADT_LOCAL_SUSPECT)
    capped = min(traffic, ADT_HARD_CAP)
    return capped, suspect


def lowest_of(*values) -> int | None:
    numbers = [n for n in (rating_int(v) for v in values) if n is not None]
    return min(numbers) if numbers else None


def worst_component(deck, superstructure, substructure, culvert) -> str | None:
    parts = {
        "deck": rating_int(deck),
        "superstructure": rating_int(superstructure),
        "substructure": rating_int(substructure),
        "culvert": rating_int(culvert),
    }
    present = {k: v for k, v in parts.items() if v is not None}
    if not present:
        return None
    low = min(present.values())
    order = ("superstructure", "deck", "substructure", "culvert")
    for name in order:
        if present.get(name) == low:
            return name
    return next(iter(present))


def unease_score(
    *,
    lowest: int | None,
    adt_capped: int,
    status: str | None,
    scour: str | None,
    fracture: str | None,
    overdue: bool,
    year_built: int | None,
    culvert: bool,
) -> int:
    condition = CONDITION_POINTS.get(lowest if lowest is not None else 7, 12)
    # Traffic scales the condition problem rather than stacking on top of it. A
    # sound bridge stays sound no matter how many people cross it; a bad one
    # matters more when it is busy.
    reach = min(1.0, math.log10(max(adt_capped, 1)) / 5.3)
    exposure = 0.60 + 0.40 * reach
    status_pts = STATUS_POINTS.get((status or "").strip().upper(), 0)
    scour_pts = 0
    scour_code = (scour or "").strip()
    if is_scour_critical(scour_code):
        scour_pts = 14
    elif scour_code == "4":
        scour_pts = 8
    fracture_pts = 8 if is_fracture_critical(fracture) else 0
    overdue_pts = 6 if overdue else 0
    age_pts = 0.0
    if year_built and year_built > 1800 and not culvert:
        age = max(0, CURRENT_YEAR - year_built)
        if age > 50:
            age_pts = min(8.0, (age - 50) / 5.0)
    culvert_pts = -18 if culvert and adt_capped < 10_000 else 0
    raw = max(
        0.0,
        condition * exposure
        + status_pts
        + scour_pts
        + fracture_pts
        + overdue_pts
        + age_pts
        + culvert_pts,
    )
    # Soft ceiling. A hard clamp flattened every bad urban bridge onto the same
    # value, which made the ranking useless exactly where it matters most.
    return int(round(98.0 * (1.0 - math.exp(-raw / 46.0))))


def headline_for(derived: dict[str, Any]) -> str:
    year = derived.get("year_built")
    phrase = derived.get("structure_type") or "structure"
    lead = f"{year} {phrase}" if year else phrase
    lead = lead[0].upper() + lead[1:] if lead else "Structure"

    worst = derived.get("worst_component")
    lowest = derived.get("lowest_rating")
    word = condition_word(lowest) if lowest is not None else None
    if worst and word:
        label = public_component(worst, title=True)
        middle = f"{label}: {word}"
    elif derived.get("bridge_condition"):
        middle = band_label(derived["bridge_condition"])
    else:
        middle = None

    adt = derived.get("adt") or 0
    suspect = derived.get("adt_suspect")
    if adt and not suspect:
        tail = f"{adt:,} vehicles a day"
    elif adt and suspect:
        tail = f"{adt:,} vehicles a day (reported)"
    else:
        tail = None

    parts = [lead + "."]
    if middle:
        parts.append(middle + ".")
    if tail:
        parts.append(tail + ".")
    return " ".join(parts)


def why_line(derived: dict[str, Any]) -> str:
    bits: list[str] = []
    worst = derived.get("worst_component")
    lowest = derived.get("lowest_rating")
    word = condition_word(lowest)
    if worst and word:
        bits.append(f"{word} {public_component(worst)}")
    status = derived.get("status_code")
    if status and status.upper() in STATUS_POINTS:
        bits.append(status_label(status))
    adt = derived.get("adt") or 0
    if adt and not derived.get("adt_suspect"):
        if adt >= 1000:
            bits.append(f"{adt / 1000:.0f}k vehicles/day" if adt >= 10_000 else f"{adt:,} vehicles/day")
        else:
            bits.append(f"{adt:,} vehicles/day")
    if derived.get("fracture_critical"):
        bits.append("fracture-critical")
    if derived.get("scour_critical"):
        bits.append("scour-critical")
    if derived.get("inspect_overdue"):
        bits.append("inspection overdue")
    return " · ".join(bits)


def derive(record: dict[str, Any], today: date | None = None) -> dict[str, Any]:
    today = today or date.today()
    deck = record.get("deck")
    superstructure = record.get("superstructure")
    substructure = record.get("substructure")
    culvert_rating = record.get("culvert")
    lowest = record.get("lowest_rating")
    if lowest is None:
        lowest = lowest_of(deck, superstructure, substructure, culvert_rating)
    year_built = record.get("year_built")
    year_rebuilt = record.get("year_reconstructed") or None
    if year_rebuilt == 0:
        year_rebuilt = None
    inspect_on = parse_inspect_date(record.get("inspect_raw"), today)
    freq = record.get("inspect_freq_months")
    overdue = inspect_overdue(inspect_on, freq, today)
    culvert = is_culvert(record.get("design_code"))
    adt = int(record.get("adt") or 0)
    capped, suspect = adt_hygiene(
        adt, record.get("functional_class"), record.get("facility_carried")
    )
    age = (today.year - year_built) if year_built and year_built > 1800 else None
    derived = {
        "lowest_rating": lowest,
        "bridge_condition": official_condition_band(
            lowest, record.get("bridge_condition")
        ),
        "year_built": year_built,
        "year_reconstructed": year_rebuilt,
        "age_years": age,
        "inspect_date": inspect_on,
        "inspect_overdue": overdue,
        "adt": adt,
        "adt_capped": capped,
        "adt_suspect": suspect,
        "is_culvert": culvert,
        "structure_type": structure_phrase(
            record.get("material_code"), record.get("design_code")
        ),
        "status_code": record.get("status_code"),
        "status_label": status_label(record.get("status_code")),
        "worst_component": worst_component(
            deck, superstructure, substructure, culvert_rating
        ),
        "fracture_critical": is_fracture_critical(record.get("fracture")),
        "scour_critical": is_scour_critical(record.get("scour")),
    }
    derived["unease_score"] = unease_score(
        lowest=lowest,
        adt_capped=capped,
        status=record.get("status_code"),
        scour=record.get("scour"),
        fracture=record.get("fracture"),
        overdue=overdue,
        year_built=year_built,
        culvert=culvert,
    )
    derived["headline"] = headline_for(derived)
    derived["why"] = why_line(derived)
    return derived
