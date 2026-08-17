"""Deterministic NBI → English. No model, no runtime guesswork."""

from __future__ import annotations

from typing import Any

from backend.lookups import (
    NBI_ITEMS,
    band_label,
    condition_word,
    normalize_scour_code,
    rating_int,
    scour_label,
)
from backend.scoring import public_component

RATING_PLAIN = {
    9: "No notable problems were reported for this component.",
    8: "Inspectors reported no significant problems, with only very minor defects if any.",
    7: "Some minor problems may be present, but the component remains in FHWA's Good condition range.",
    6: "Deterioration is present, but the component remains above FHWA's Fair and Poor categories.",
    5: (
        "The component remains structurally serviceable, but inspectors reported "
        "deterioration such as minor section loss, cracking, spalling, scour, or similar defects."
    ),
    4: (
        "Inspectors reported advanced deterioration in this component. A rating of 4 "
        "places the bridge in FHWA's Poor condition category. Poor is an official "
        "condition category. It does not by itself mean the bridge is unsafe or about to fail."
    ),
    3: (
        "Inspectors reported serious deterioration. The component's condition or remaining "
        "capacity is well below as-built. This is an official condition rating, not a "
        "prediction that the structure will fail."
    ),
    2: (
        "Inspectors reported critical deterioration. The component is typically closely "
        "monitored, and corrective action may be necessary."
    ),
    1: (
        "This is the official designation for a component in imminent failure. It is a "
        "federal inventory rating; current local restrictions or closures may differ."
    ),
    0: (
        "This is the bottom official rating. It generally means the component is out of service."
    ),
}

STATUS_PLAIN = {
    "A": "The structure is reported open to traffic.",
    "B": (
        "Engineers have identified a need for a load restriction, but this inventory "
        "does not show that posting as already in place."
    ),
    "P": (
        "The bridge remains open, but heavier vehicle loads are restricted because the "
        "structure cannot carry the full range of normally permitted highway loads."
    ),
    "R": "The bridge remains open with a restriction other than a standard load posting.",
    "D": "Temporary structural support is being used.",
    "E": "The inventory reports a temporary structure in place.",
    "K": "The structure is reported closed. This record does not by itself say why.",
    "G": "The structure is reported as not yet open.",
}

SCOUR_PLAIN = {
    "N": "The inventory does not list this structure as spanning water.",
    "9": "Foundations are reported above flood elevations, or the site is dry.",
    "8": "Foundations were evaluated as stable for the calculated or observed scour.",
    "7": "Scour countermeasures are reported as installed.",
    "6": "A scour evaluation is reported as not completed.",
    "5": "Foundations were evaluated as stable for the calculated or observed scour.",
    "4": (
        "Foundations are reported as currently stable, but a field review indicates "
        "that protective action is required. This code is not scour-critical."
    ),
    "3": (
        "Scour is erosion of soil or sediment around bridge foundations caused by moving "
        "water. This record rates the structure as scour-critical: foundations were "
        "evaluated as unstable under the assessed or calculated scour."
    ),
    "2": (
        "Scour is erosion of soil or sediment around bridge foundations caused by moving "
        "water. This record rates the structure as scour-critical: extensive scour has "
        "been observed or evaluated, and foundations are considered unstable."
    ),
    "1": (
        "Scour is erosion of soil or sediment around bridge foundations caused by moving "
        "water. This official code means failure from scour is considered imminent and "
        "the bridge is reported closed."
    ),
    "0": (
        "Scour is erosion of soil or sediment around bridge foundations caused by moving "
        "water. This official code means the bridge failed from scour and is closed."
    ),
    "U": (
        "The foundation type is unknown and has not been evaluated for scour. "
        "This code is not scour-critical."
    ),
    "T": (
        "This is reported as a tidal bridge that has not been evaluated for scour "
        "and is considered low risk."
    ),
}

REDUNDANCY_PLAIN = (
    "Certain steel tension members have limited alternate load paths if one fractures. "
    "This increases the consequence of a member failure, so those members receive "
    "specialized inspection. The designation does not mean inspectors found a crack "
    "or fracture."
)

TRAFFIC_PLAIN = (
    "Traffic does not change the inspector's condition rating. It affects this site's "
    "score because deterioration or restrictions on a heavily used bridge affect more travelers."
)

INSPECT_PLAIN = (
    "Based on the inspection date and interval contained in this NBI record, another "
    "inspection appears due or past due. State or local records may be newer than the "
    "federal inventory snapshot."
)

SCORE_CAVEAT = (
    "These factors lower this site's Bridge Score, but the score is not an official "
    "FHWA safety grade and does not mean failure is expected."
)

METHODOLOGY = (
    "FHWA supplies the official inspection ratings and Good/Fair/Poor condition. "
    "This site calculates the 0–100 Bridge Score to make bridges easier to compare. "
    "The score is not an FHWA grade, engineering inspection, or safety determination. "
    "NBI data may lag newer state or local records."
)

STATUS_TITLES = {
    "B": "Posting recommended",
    "P": "Load restricted",
    "R": "Other restriction",
    "D": "Temporarily shored",
    "E": "Temporary structure",
    "K": "Closed",
    "G": "Not yet open",
}


def rating_plain(value) -> str | None:
    number = value if isinstance(value, int) else rating_int(value)
    if number is None:
        return None
    return RATING_PLAIN.get(number)


def status_plain(code: str | None) -> str | None:
    return STATUS_PLAIN.get((code or "").strip().upper())


def scour_plain(code: str | None) -> str | None:
    return SCOUR_PLAIN.get(normalize_scour_code(code))


def _iso(value) -> str | None:
    if value is None:
        return None
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def _month_name(value) -> str | None:
    if value is None:
        return None
    names = (
        "January",
        "February",
        "March",
        "April",
        "May",
        "June",
        "July",
        "August",
        "September",
        "October",
        "November",
        "December",
    )
    month = getattr(value, "month", None)
    year = getattr(value, "year", None)
    if not month or not year:
        return None
    return f"{names[month - 1]} {year}"


def _adt_clause(adt: int, suspect: bool) -> str | None:
    if not adt:
        return None
    count = f"{int(adt):,}"
    if suspect:
        return f"About {count} vehicles a day are reported on this record."
    return f"About {count} vehicles use the bridge each day."


def _component_lead(derived: dict[str, Any]) -> str | None:
    worst = derived.get("worst_component")
    lowest = derived.get("lowest_rating")
    if worst is None or lowest is None:
        band = derived.get("bridge_condition")
        if band:
            return (
                f"The official FHWA condition category for this structure is "
                f"{band_label(band)}."
            )
        return "Official component ratings are not present in this inventory record."
    name = public_component(worst)
    word = condition_word(lowest)
    rated = f"{lowest}/9"
    if word:
        rated = f"{lowest}/9 ({word})"
    band = derived.get("bridge_condition")
    lead = f"The bridge's {name} is rated {rated}"
    if band == "P":
        return f"{lead}, which places the bridge in FHWA's Poor condition category."
    if band == "F":
        return f"{lead}, which places the bridge in FHWA's Fair condition category."
    if band == "G":
        return f"{lead}, which places the bridge in FHWA's Good condition category."
    return f"{lead}."


def _status_follow(code: str | None) -> str | None:
    raw = (code or "").strip().upper()
    if raw == "P":
        return "It is also load restricted, meaning heavier vehicles are limited."
    if raw == "B":
        return (
            "A load restriction has been recommended, but posting is not shown as "
            "already in place."
        )
    if raw == "R":
        return "It is open with a restriction other than a standard load posting."
    if raw == "D":
        return "Temporary structural support is reported in place."
    if raw == "E":
        return "The inventory reports a temporary structure."
    if raw == "K":
        return "The structure is reported closed."
    return None


def _flag_clause(derived: dict[str, Any]) -> str | None:
    bits: list[str] = []
    scour = normalize_scour_code(derived.get("scour"))
    if scour in {"0", "1", "2", "3"}:
        bits.append("its foundations are identified as vulnerable to scour")
    elif scour == "4":
        bits.append("a field review has indicated that scour protection is required")
    elif scour == "U":
        bits.append("the foundation type is unknown and has not been evaluated for scour")
    elif scour == "6":
        bits.append("a scour evaluation has not been completed")
    elif scour == "T":
        bits.append("it is a tidal structure that has not been evaluated for scour")
    if derived.get("fracture_critical"):
        bits.append("parts of the structure have limited structural redundancy")
    if not bits:
        return None
    if len(bits) == 1:
        clause = bits[0]
        return clause[:1].upper() + clause[1:] + "."
    return f"{bits[0][:1].upper() + bits[0][1:]}, and {bits[1]}."


def _inspect_clause(derived: dict[str, Any]) -> str | None:
    if not derived.get("inspect_overdue"):
        return None
    due = _month_name(derived.get("inspect_due_on"))
    past = derived.get("inspect_months_past_due")
    if due and past:
        return (
            f"Based on the inspection date and interval in this NBI record, another "
            f"inspection appears past due (implied due date {due}, about {past} "
            f"{'month' if past == 1 else 'months'} past that date). State or "
            f"local records may be newer than the federal inventory snapshot."
        )
    return INSPECT_PLAIN


def summary_paragraphs(derived: dict[str, Any]) -> list[str]:
    paragraphs: list[str] = []
    lead = _component_lead(derived)
    follow = _status_follow(derived.get("status_code"))
    if lead and follow:
        paragraphs.append(f"{lead} {follow}")
    elif lead:
        paragraphs.append(lead)

    second_bits: list[str] = []
    flags = _flag_clause(derived)
    if flags:
        second_bits.append(flags)
    traffic = _adt_clause(derived.get("adt") or 0, bool(derived.get("adt_suspect")))
    if traffic:
        second_bits.append(traffic)
    inspect = _inspect_clause(derived)
    if inspect:
        second_bits.append(inspect)
    if second_bits:
        paragraphs.append(" ".join(second_bits))

    breakdown = derived.get("score_breakdown") or {}
    deducted = sum(
        int(breakdown.get(key) or 0)
        for key in (
            "status_deduction",
            "scour_deduction",
            "redundancy_deduction",
            "inspection_deduction",
            "traffic_deduction",
        )
    )
    score = derived.get("score")
    if deducted or (score is not None and score < 70):
        paragraphs.append(SCORE_CAVEAT)
    elif traffic and (derived.get("lowest_rating") is None or derived["lowest_rating"] >= 7):
        paragraphs.append(
            "Traffic does not change the inspector's condition rating."
        )
    return paragraphs


def _driver(
    *,
    key: str,
    title: str,
    status: str | None,
    value: str | None,
    plain: str,
    technical: str | None,
    score_effect: int | None,
) -> dict[str, Any]:
    row = {
        "key": key,
        "title": title,
        "status": status,
        "value": value,
        "plain": plain,
        "technical": technical,
        "score_effect": score_effect,
    }
    return {k: v for k, v in row.items() if v is not None}


def explanations(derived: dict[str, Any], record: dict[str, Any] | None = None) -> list[dict]:
    record = record or {}
    rows: list[dict] = []
    breakdown = derived.get("score_breakdown") or {}
    worst = derived.get("worst_component")
    lowest = derived.get("lowest_rating")
    word = condition_word(lowest) if lowest is not None else None
    if worst and lowest is not None and lowest <= 6:
        nbi = NBI_ITEMS.get(worst)
        base = int(breakdown.get("condition_base") or 0)
        rows.append(
            _driver(
                key=worst,
                title=public_component(worst, title=True),
                status=word,
                value=f"{lowest}/9",
                plain=rating_plain(lowest) or "",
                technical=f"NBI Item {nbi}" if nbi else None,
                score_effect=base - 98,
            )
        )

    status = (derived.get("status_code") or "").strip().upper()
    status_pts = int(breakdown.get("status_deduction") or 0)
    if status_pts or status in STATUS_TITLES:
        if status in STATUS_TITLES:
            rows.append(
                _driver(
                    key="status",
                    title=STATUS_TITLES[status],
                    status=derived.get("status_label"),
                    value=status,
                    plain=status_plain(status) or "",
                    technical=f"NBI Item {NBI_ITEMS['status']}",
                    score_effect=-status_pts if status_pts else 0,
                )
            )

    scour = normalize_scour_code(derived.get("scour") or (record.get("scour") if record else None))
    scour_pts = int(breakdown.get("scour_deduction") or 0)
    if scour_pts or scour in {"0", "1", "2", "3", "4", "U", "6", "T"}:
        title = "Scour vulnerability" if scour in {"0", "1", "2", "3"} else "Scour"
        if scour == "4":
            title = "Scour — protective action required"
        elif scour == "U":
            title = "Scour — unknown foundation"
        elif scour == "6":
            title = "Scour — evaluation not completed"
        rows.append(
            _driver(
                key="scour",
                title=title,
                status=scour_label(scour),
                value=scour or None,
                plain=scour_plain(scour) or "",
                technical=f"NBI Item {NBI_ITEMS['scour']}",
                score_effect=-scour_pts if scour_pts else 0,
            )
        )

    if derived.get("fracture_critical"):
        redun = int(breakdown.get("redundancy_deduction") or 0)
        rows.append(
            _driver(
                key="redundancy",
                title="Limited structural redundancy",
                status="NSTM",
                value="Y",
                plain=REDUNDANCY_PLAIN,
                technical='NSTM · legacy "fracture-critical" designation · NBI Item 92A',
                score_effect=-redun if redun else -4,
            )
        )

    if derived.get("inspect_overdue"):
        inspect_pts = int(breakdown.get("inspection_deduction") or 0)
        inspected = _month_name(derived.get("inspect_date"))
        due = _month_name(derived.get("inspect_due_on"))
        freq = derived.get("inspect_freq_months")
        bits = [INSPECT_PLAIN]
        if inspected and freq:
            bits.append(f"Reported inspection: {inspected}. Interval: {freq} months.")
        if due:
            bits.append(f"Next inspection implied by this record: {due}.")
        rows.append(
            _driver(
                key="inspection",
                title="Reported inspection timing",
                status="Past due" if derived.get("inspect_overdue") else None,
                value=due,
                plain=" ".join(bits),
                technical=f"NBI Items {NBI_ITEMS['inspect_date']} and {NBI_ITEMS['inspect_freq']}",
                score_effect=-inspect_pts if inspect_pts else -2,
            )
        )

    traffic_pts = int(breakdown.get("traffic_deduction") or 0)
    adt = int(derived.get("adt") or 0)
    if traffic_pts and adt and not derived.get("adt_suspect"):
        rows.append(
            _driver(
                key="traffic",
                title="Traffic",
                status=None,
                value=f"{adt:,} / day",
                plain=f"{_adt_clause(adt, False)} {TRAFFIC_PLAIN}",
                technical=f"NBI Item {NBI_ITEMS['adt']}",
                score_effect=-traffic_pts,
            )
        )
    return rows


def component_explanations(record: dict[str, Any]) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for key in ("deck", "superstructure", "substructure", "culvert"):
        raw = record.get(key)
        value = rating_int(raw)
        if value is None:
            continue
        out[key] = {
            "code": raw,
            "value": value,
            "word": condition_word(value),
            "plain": rating_plain(value),
            "nbi_item": NBI_ITEMS[key],
        }
    return out


def describe(derived: dict[str, Any], record: dict[str, Any] | None = None) -> dict[str, Any]:
    from backend.scoring import headline_for, why_line

    record = record or {}
    paras = summary_paragraphs(derived)
    drivers = explanations(derived, record)
    payload = {
        "summary": " ".join(paras),
        "summary_paragraphs": paras,
        "explanations": drivers,
        "methodology": METHODOLOGY,
        "headline": headline_for(derived),
    }
    derived_with = dict(derived)
    derived_with["explanations"] = drivers
    payload["why"] = why_line(derived_with)
    return payload


def explain_bridge(bridge: Any, today=None) -> dict[str, Any]:
    from backend.scoring import derive, record_from_bridge

    return derive(record_from_bridge(bridge), today=today)


def structure_intro(
    phrase: str | None,
    maintainer: str | None = None,
    owner: str | None = None,
) -> str | None:
    who = maintainer or owner
    if phrase and who:
        return f"This is a {phrase}. Maintenance is reported as {who}."
    if phrase:
        return f"This is a {phrase}."
    if who:
        return f"Maintenance is reported as {who}."
    return None


def dimensions_note(deck_area_label: str | None) -> str | None:
    if not deck_area_label:
        return None
    return (
        "Span dimensions affect structural design and load distribution. "
        f"The deck area of {deck_area_label} is the reported surface to maintain."
    )


def load_ratings_paragraph(
    operating_label: str | None,
    inventory_label: str | None,
    operating_tons: float | None = None,
    posted: bool = False,
) -> str | None:
    bits: list[str] = []
    if operating_label:
        bits.append(
            f"The operating rating of {operating_label} is the reported maximum load "
            "under controlled conditions with special permits."
        )
    if inventory_label:
        bits.append(
            f"The inventory rating of {inventory_label} is the reported load level "
            "for everyday traffic without extra restrictions."
        )
    if operating_tons is not None and operating_tons < 20:
        bits.append(
            "These relatively low ratings may result in posted weight limits "
            "or route restrictions for heavy vehicles."
        )
    if posted:
        bits.append("This record already shows a load posting.")
    return " ".join(bits) or None
