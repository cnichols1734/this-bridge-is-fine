"""NBI code tables. Words we print, not invent."""

from __future__ import annotations

CONDITION_WORDS = {
    9: "Excellent",
    8: "Very good",
    7: "Good",
    6: "Satisfactory",
    5: "Fair",
    4: "Poor",
    3: "Serious",
    2: "Critical",
    1: "Imminent failure",
    0: "Failed",
}

CONDITION_BAND = {
    "G": "Good",
    "F": "Fair",
    "P": "Poor",
}

STATUS_41 = {
    "A": "Open",
    "B": "Open — posting recommended",
    "D": "Open — temporarily shored",
    "E": "Open — temporary structure",
    "G": "Not yet open",
    "K": "Closed",
    "P": "Posted for load",
    "R": "Posted — other restriction",
}

MATERIAL_43A = {
    "1": "concrete",
    "2": "continuous concrete",
    "3": "steel",
    "4": "continuous steel",
    "5": "prestressed concrete",
    "6": "continuous prestressed concrete",
    "7": "timber",
    "8": "masonry",
    "9": "aluminum or iron",
    "0": "other",
}

DESIGN_43B = {
    "01": "slab",
    "02": "girder",
    "03": "girder and floorbeam",
    "04": "tee beam",
    "05": "box beam",
    "06": "box girder",
    "07": "frame",
    "08": "orthotropic",
    "09": "deck truss",
    "10": "thru-truss",
    "11": "deck arch",
    "12": "thru-arch",
    "13": "suspension",
    "14": "cable-stayed",
    "15": "movable — lift",
    "16": "movable — bascule",
    "17": "movable — swing",
    "18": "tunnel",
    "19": "culvert",
    "20": "mixed types",
    "21": "segmental box girder",
    "22": "channel beam",
}

# Interstate / freeway / expressway in item 26.
FREEWAY_CLASSES = {"01", "1", "11", "12"}

COMPONENT_LABELS = {
    "deck": "Deck",
    "superstructure": "Superstructure",
    "substructure": "Substructure",
    "culvert": "Culvert",
}

PUBLIC_COMPONENT_LABELS = {
    "deck": "Road surface",
    "superstructure": "Support structure",
    "substructure": "Foundation",
    "culvert": "Culvert",
}

NBI_ITEMS = {
    "deck": "58",
    "superstructure": "59",
    "substructure": "60",
    "culvert": "62",
    "status": "41",
    "scour": "113",
    "fracture": "92A",
    "inspect_date": "90",
    "inspect_freq": "91",
    "adt": "29",
}

# Item 113. Codes 0–3 are the official scour-critical set. 4 and U are not.
SCOUR_CODES = {
    "N": "Not over water",
    "9": "Foundations above flood elevations",
    "8": "Evaluated as stable",
    "7": "Countermeasures installed",
    "6": "Scour evaluation not completed",
    "5": "Evaluated as stable",
    "4": "Stable; protective action required",
    "3": "Scour-critical; foundations unstable under assessed scour",
    "2": "Scour-critical; extensive scour, foundations unstable",
    "1": "Failure considered imminent; closed",
    "0": "Failed from scour and closed",
    "U": "Unknown foundation; not evaluated for scour",
    "T": "Tidal; not evaluated, considered low risk",
}


def _code(value) -> str:
    if value is None:
        return ""
    return str(value).strip()


def rating_int(value) -> int | None:
    raw = _code(value)
    if raw in {"", "N", "n"}:
        return None
    try:
        return int(raw)
    except ValueError:
        return None


def condition_word(value) -> str | None:
    number = rating_int(value) if not isinstance(value, int) else value
    if number is None:
        return None
    return CONDITION_WORDS.get(number)


def status_label(code: str | None) -> str:
    return STATUS_41.get(_code(code).upper(), "Unknown")


def material_label(code: str | None) -> str | None:
    return MATERIAL_43A.get(_code(code)[:1] or "", None)


def design_label(code: str | None) -> str | None:
    raw = _code(code)
    if not raw:
        return None
    if len(raw) == 1:
        raw = raw.zfill(2)
    return DESIGN_43B.get(raw)


def structure_phrase(material_code: str | None, design_code: str | None) -> str:
    material = material_label(material_code)
    design = design_label(design_code)
    if material and design:
        if design == "culvert":
            return f"{material} culvert"
        return f"{material} {design}"
    return material or design or "structure"


def is_freeway(functional_class: str | None, facility_carried: str | None) -> bool:
    code = _code(functional_class).zfill(2) if _code(functional_class) else ""
    if code in FREEWAY_CLASSES or _code(functional_class) in FREEWAY_CLASSES:
        return True
    name = (facility_carried or "").upper()
    return "INTERSTATE" in name or name.startswith("I-") or name.startswith("I ")


def is_culvert(design_code: str | None) -> bool:
    raw = _code(design_code)
    return raw.zfill(2) == "19" if raw else False


def is_fracture_critical(value: str | None) -> bool:
    return _code(value).upper().startswith("Y")


def normalize_scour_code(value: str | None) -> str:
    raw = _code(value)
    if not raw:
        return ""
    upper = raw.upper()
    if upper in {"N", "U", "T"}:
        return upper
    return raw


def scour_label(value: str | None) -> str | None:
    code = normalize_scour_code(value)
    return SCOUR_CODES.get(code)


def is_scour_critical(value: str | None) -> bool:
    """Official scour-critical codes only: 0, 1, 2, 3. Not 4. Not U."""
    return normalize_scour_code(value) in {"0", "1", "2", "3"}


def band_label(code: str | None) -> str:
    return CONDITION_BAND.get(_code(code).upper(), "Unknown")


def official_condition_band(lowest, source: str | None = None) -> str | None:
    """Official NBI G/F/P. Trust the source item; fill from lowest rating if missing.

    FHWA: G = 7–9, F = 5–6, P = 0–4. This is not the site-generated Bridge Score.
    """
    raw = _code(source).upper()
    if raw in CONDITION_BAND:
        return raw
    number = lowest if isinstance(lowest, int) else rating_int(lowest)
    if number is None:
        return None
    if number >= 7:
        return "G"
    if number >= 5:
        return "F"
    if number >= 0:
        return "P"
    return None
