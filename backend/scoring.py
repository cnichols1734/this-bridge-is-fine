"""Derived fields. This is the product."""

from __future__ import annotations

import math
from datetime import date, datetime
from typing import Any

from backend.lookups import (
    PUBLIC_COMPONENT_LABELS,
    band_label,
    condition_word,
    is_culvert,
    is_fracture_critical,
    is_freeway,
    is_scour_critical,
    normalize_scour_code,
    official_condition_band,
    rating_int,
    status_label,
    structure_phrase,
)

COMPONENT_PUBLIC = {
    key: label.lower() for key, label in PUBLIC_COMPONENT_LABELS.items()
}

# Worst applicable official component → public Bridge Score base.
# Higher is better. 4/9 Poor sits in the middle of the scale, not at zero.
CONDITION_BASE = {
    9: 98,
    8: 93,
    7: 86,
    6: 76,
    5: 66,
    4: 54,
    3: 40,
    2: 25,
    1: 10,
    0: 0,
}
# Missing ratings are not Good.
MISSING_CONDITION_BASE = 70

STATUS_DEDUCTION = {
    "A": 0,
    "B": 3,
    "P": 6,
    "R": 4,
    "D": 8,
    "E": 4,
    "K": 4,
}

SCOUR_DEDUCTION = {
    "N": 0,
    "9": 0,
    "8": 0,
    "7": 0,
    "5": 0,
    "T": 1,
    "6": 2,
    "U": 3,
    "4": 3,
    "3": 6,
    "2": 10,
    "1": 16,
    "0": 20,
}

REDUNDANCY_DEDUCTION = 4
INSPECTION_DEDUCTION = 2
MAX_TRAFFIC_PENALTY = 5
UNKNOWN_CONDITION_SEVERITY = 0.25

CONDITION_SEVERITY = {
    9: 0.0,
    8: 0.05,
    7: 0.10,
    6: 0.20,
    5: 0.35,
    4: 0.55,
    3: 0.80,
    2: 0.95,
    1: 1.0,
    0: 1.0,
}

SCORE_BANDS = (
    (85, "Few concerns"),
    (70, "Some concerns"),
    (55, "Moderate concerns"),
    (40, "Elevated concerns"),
    (0, "Significant concerns"),
)

CURRENT_YEAR = date.today().year
ADT_HARD_CAP = 350_000
ADT_ABSURD = 400_000
ADT_LOCAL_SUSPECT = 150_000
BREAKDOWN_KEYS = (
    "condition_base",
    "status_deduction",
    "scour_deduction",
    "redundancy_deduction",
    "inspection_deduction",
    "traffic_deduction",
    "score",
    "score_band",
)


def public_component(key: str | None, title: bool = False) -> str:
    label = COMPONENT_PUBLIC.get(key or "", key or "")
    return label[:1].upper() + label[1:] if title and label else label


def publicize_text(text: str | None) -> str | None:
    """Rewrite stored NBI jargon for the file the public reads."""
    if not text:
        return text
    pairs = (
        ("Superstructure", "Support structure"),
        ("superstructure", "support structure"),
        ("Substructure", "Foundation"),
        ("substructure", "foundation"),
        ("Deck", "Road surface"),
        ("deck", "road surface"),
    )
    out = text
    for old, new in pairs:
        out = out.replace(old, new)
    return out


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
    return date(year, month0 + 1, 1)


def months_between(start: date, end: date) -> int:
    return (end.year - start.year) * 12 + (end.month - start.month)


def _as_date(value) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return None


def inspect_timing(
    inspect_on: date | None,
    freq_months: int | None,
    today: date | None = None,
) -> dict[str, Any]:
    today = today or date.today()
    start = _as_date(inspect_on)
    freq = int(freq_months) if freq_months else 0
    if not start or freq <= 0:
        return {
            "inspect_date": start,
            "inspect_freq_months": freq_months if freq_months else None,
            "inspect_due_on": None,
            "inspect_months_past_due": None,
            "inspect_overdue": False,
        }
    due = add_months(start, freq)
    overdue = today >= due
    past = months_between(due, today) if overdue else 0
    return {
        "inspect_date": start,
        "inspect_freq_months": freq,
        "inspect_due_on": due,
        "inspect_months_past_due": past if overdue else 0,
        "inspect_overdue": overdue,
    }


def inspect_overdue(
    inspect_on: date | None, freq_months: int | None, today: date | None = None
) -> bool:
    return bool(inspect_timing(inspect_on, freq_months, today)["inspect_overdue"])


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


def score_band(score: int | None) -> str:
    if score is None:
        return "Significant concerns"
    number = int(score)
    for threshold, label in SCORE_BANDS:
        if number >= threshold:
            return label
    return "Significant concerns"


def traffic_deduction(
    adt_capped: int,
    lowest: int | None,
    *,
    suspect: bool = False,
) -> int:
    """Exposure, not deterioration. Bounded, and almost none when condition is Good."""
    if suspect or adt_capped <= 0:
        return 0
    reach = min(1.0, math.log10(max(adt_capped, 1)) / 5.3)
    severity = CONDITION_SEVERITY.get(
        lowest if lowest is not None else -1, UNKNOWN_CONDITION_SEVERITY
    )
    return int(round(reach * severity * MAX_TRAFFIC_PENALTY))


def score_breakdown(
    *,
    lowest: int | None,
    adt_capped: int,
    status: str | None,
    scour: str | None,
    fracture: str | None,
    overdue: bool,
    adt_suspect: bool = False,
    year_built: int | None = None,
    culvert: bool = False,
) -> dict[str, Any]:
    """Public Bridge Score. Higher is better. Age and culvert type do not deduct."""
    del year_built, culvert
    if lowest is None:
        base = MISSING_CONDITION_BASE
    else:
        base = CONDITION_BASE.get(lowest, MISSING_CONDITION_BASE)
    status_pts = STATUS_DEDUCTION.get((status or "").strip().upper(), 0)
    scour_pts = SCOUR_DEDUCTION.get(normalize_scour_code(scour), 0)
    redundancy_pts = REDUNDANCY_DEDUCTION if is_fracture_critical(fracture) else 0
    inspect_pts = INSPECTION_DEDUCTION if overdue else 0
    traffic_pts = traffic_deduction(adt_capped, lowest, suspect=adt_suspect)
    raw = base - status_pts - scour_pts - redundancy_pts - inspect_pts - traffic_pts
    score = max(0, min(100, int(round(raw))))
    return {
        "condition_base": base,
        "status_deduction": status_pts,
        "scour_deduction": scour_pts,
        "redundancy_deduction": redundancy_pts,
        "inspection_deduction": inspect_pts,
        "traffic_deduction": traffic_pts,
        "score": score,
        "score_band": score_band(score),
    }


def bridge_score(
    *,
    lowest: int | None,
    adt_capped: int,
    status: str | None,
    scour: str | None,
    fracture: str | None,
    overdue: bool,
    adt_suspect: bool = False,
    year_built: int | None = None,
    culvert: bool = False,
) -> int:
    return score_breakdown(
        lowest=lowest,
        adt_capped=adt_capped,
        status=status,
        scour=scour,
        fracture=fracture,
        overdue=overdue,
        adt_suspect=adt_suspect,
        year_built=year_built,
        culvert=culvert,
    )["score"]


def unease_score(
    *,
    lowest: int | None,
    adt_capped: int,
    status: str | None,
    scour: str | None,
    fracture: str | None,
    overdue: bool,
    year_built: int | None = None,
    culvert: bool = False,
    adt_suspect: bool = False,
) -> int:
    """Stored column. Value is the public Bridge Score (higher is better)."""
    return bridge_score(
        lowest=lowest,
        adt_capped=adt_capped,
        status=status,
        scour=scour,
        fracture=fracture,
        overdue=overdue,
        adt_suspect=adt_suspect,
        year_built=year_built,
        culvert=culvert,
    )


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
    for row in derived.get("explanations") or []:
        title = row.get("title")
        if title:
            bits.append(title)
    if bits:
        return " · ".join(bits)
    worst = derived.get("worst_component")
    lowest = derived.get("lowest_rating")
    word = condition_word(lowest)
    if worst and word:
        bits.append(f"{word} {public_component(worst)}")
    return " · ".join(bits)


def record_from_bridge(bridge: Any) -> dict[str, Any]:
    """Enough stored columns to re-derive score and copy without a new ingest."""
    return {
        "deck": getattr(bridge, "deck", None),
        "superstructure": getattr(bridge, "superstructure", None),
        "substructure": getattr(bridge, "substructure", None),
        "culvert": getattr(bridge, "culvert", None),
        "lowest_rating": getattr(bridge, "lowest_rating", None),
        "bridge_condition": getattr(bridge, "bridge_condition", None),
        "status_code": getattr(bridge, "status_code", None),
        "scour": getattr(bridge, "scour", None),
        "fracture": getattr(bridge, "fracture", None),
        "year_built": getattr(bridge, "year_built", None),
        "year_reconstructed": getattr(bridge, "year_reconstructed", None),
        "adt": getattr(bridge, "adt", None),
        "inspect_raw": getattr(bridge, "inspect_raw", None),
        "inspect_date": getattr(bridge, "inspect_date", None),
        "inspect_freq_months": getattr(bridge, "inspect_freq_months", None),
        "functional_class": getattr(bridge, "functional_class", None),
        "facility_carried": getattr(bridge, "facility_carried", None),
        "material_code": getattr(bridge, "material_code", None),
        "design_code": getattr(bridge, "design_code", None),
    }


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
    inspect_on = _as_date(record.get("inspect_date"))
    if inspect_on is None:
        inspect_on = parse_inspect_date(record.get("inspect_raw"), today)
    freq = record.get("inspect_freq_months")
    timing = inspect_timing(inspect_on, freq, today)
    culvert = is_culvert(record.get("design_code"))
    adt = int(record.get("adt") or 0)
    capped, suspect = adt_hygiene(
        adt, record.get("functional_class"), record.get("facility_carried")
    )
    age = (today.year - year_built) if year_built and year_built > 1800 else None
    status = record.get("status_code")
    scour = record.get("scour")
    fracture = record.get("fracture")
    overdue = timing["inspect_overdue"]
    breakdown = score_breakdown(
        lowest=lowest,
        adt_capped=capped,
        status=status,
        scour=scour,
        fracture=fracture,
        overdue=overdue,
        adt_suspect=suspect,
    )
    derived = {
        "lowest_rating": lowest,
        "bridge_condition": official_condition_band(
            lowest, record.get("bridge_condition")
        ),
        "year_built": year_built,
        "year_reconstructed": year_rebuilt,
        "age_years": age,
        "inspect_date": timing["inspect_date"],
        "inspect_freq_months": timing["inspect_freq_months"],
        "inspect_due_on": timing["inspect_due_on"],
        "inspect_months_past_due": timing["inspect_months_past_due"],
        "inspect_overdue": overdue,
        "adt": adt,
        "adt_capped": capped,
        "adt_suspect": suspect,
        "is_culvert": culvert,
        "structure_type": structure_phrase(
            record.get("material_code"), record.get("design_code")
        ),
        "status_code": status,
        "status_label": status_label(status),
        "worst_component": worst_component(
            deck, superstructure, substructure, culvert_rating
        ),
        "fracture_critical": is_fracture_critical(fracture),
        "scour_critical": is_scour_critical(scour),
        "scour": normalize_scour_code(scour) or None,
        "score": breakdown["score"],
        "unease_score": breakdown["score"],
        "score_band": breakdown["score_band"],
        "score_breakdown": {key: breakdown[key] for key in BREAKDOWN_KEYS},
    }
    from backend.explain import describe

    derived.update(describe(derived, record))
    derived["headline"] = derived.get("headline") or headline_for(derived)
    derived["why"] = derived.get("why") or why_line(derived)
    return derived
