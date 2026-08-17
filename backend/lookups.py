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


AGENCY_21_22 = {
    "01": "State Highway Agency",
    "02": "County Highway Agency",
    "03": "Town or Township Highway Agency",
    "04": "City or Municipal Highway Agency",
    "11": "State Park, Forest, or Reservation Agency",
    "12": "Local Park, Forest, or Reservation Agency",
    "21": "Other State Agency",
    "25": "Other Local Agency",
    "26": "Private (other than railroad)",
    "27": "Railroad",
    "31": "State Toll Authority",
    "32": "Local Toll Authority",
    "60": "Other Federal Agency",
    "61": "Indian Tribal Government",
    "62": "Bureau of Indian Affairs",
    "63": "U.S. Fish and Wildlife Service",
    "64": "U.S. Forest Service",
    "66": "National Park Service",
    "67": "Tennessee Valley Authority",
    "68": "Bureau of Land Management",
    "69": "Bureau of Reclamation",
    "70": "Corps of Engineers",
    "80": "Unknown",
}

ROUTE_PREFIX_5B = {
    "1": "Interstate",
    "2": "U.S. highway",
    "3": "State highway",
    "4": "County road",
    "5": "City street",
    "6": "Federal lands road",
    "7": "State lands road",
    "8": "Other",
}

TOLL_20 = {
    "1": "Yes",
    "2": "On a toll road",
    "3": "No",
    "4": "Interstate toll segment",
    "5": "Toll, not in use",
}

HISTORY_37 = {
    "1": "Listed on NRHP",
    "2": "Eligible for NRHP",
    "3": "Possibly eligible",
    "4": "Not determinable",
    "5": "Not eligible",
}

RATING_METH_63 = {
    "0": "Reported, assigned",
    "1": "Load Factor",
    "2": "Allowable Stress",
    "3": "Load and Resistance Factor",
    "4": "Load testing",
    "5": "No rating analysis",
    "6": "Assigned by rating factor",
    "N": "Not applicable",
}

M_TO_FT = 3.280839895
KM_TO_MI = 0.621371192
M2_TO_FT2 = 10.76391041671
TONNE_TO_SHORT_TON = 1.1023113109


def _pad2(value: str | None) -> str:
    raw = _code(value)
    if not raw:
        return ""
    if raw.isdigit():
        return raw.zfill(2)[-2:]
    return raw.upper()


def agency_label(code: str | None) -> str | None:
    raw = _pad2(code)
    return AGENCY_21_22.get(raw) or AGENCY_21_22.get(_code(code))


def route_prefix_label(code: str | None) -> str | None:
    raw = _code(code)
    if raw.isdigit():
        raw = str(int(raw))
    return ROUTE_PREFIX_5B.get(raw)


def toll_label(code: str | None) -> str | None:
    raw = _code(code)
    if raw.isdigit():
        raw = str(int(raw))
    return TOLL_20.get(raw)


def historic_label(code: str | None) -> str | None:
    raw = _code(code)
    if raw.isdigit():
        raw = str(int(raw))
    return HISTORY_37.get(raw)


def rating_method_label(code: str | None) -> str | None:
    raw = _code(code).upper()
    return RATING_METH_63.get(raw)


def parse_optional_int(value) -> int | None:
    if value in (None, "", "N", "n"):
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def parse_optional_float(value) -> float | None:
    if value in (None, "", "N", "n"):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def parse_load_rating(value) -> float | None:
    number = parse_optional_float(value)
    if number is None or number >= 99:
        return None
    return number


def short_tons(metric_tons: float | None) -> float | None:
    if metric_tons is None:
        return None
    return round(metric_tons * TONNE_TO_SHORT_TON, 1)


def format_length_m(meters: float | None) -> str | None:
    number = parse_optional_float(meters)
    if number is None:
        return None
    feet = number * M_TO_FT
    if feet >= 100:
        return f"{round(feet):,} ft ({number:,.1f} m)"
    return f"{feet:.1f} ft ({number:.1f} m)"


def format_area_m2(area: float | None) -> str | None:
    number = parse_optional_float(area)
    if number is None:
        return None
    sqft = number * M2_TO_FT2
    return f"{round(sqft):,} sq ft"


def format_detour_km(km: int | None) -> str | None:
    if km is None:
        return None
    if km == 0:
        return "On site"
    miles = km * KM_TO_MI
    if km >= 199:
        return f"{round(miles):,} mi or more ({km} km)"
    if miles >= 10:
        return f"{round(miles):,} mi ({km} km)"
    return f"{miles:.1f} mi ({km} km)"


def format_tons(metric_tons: float | None) -> str | None:
    tons = short_tons(metric_tons)
    if tons is None:
        return None
    text = f"{tons:.1f}".rstrip("0").rstrip(".")
    return f"{text} tons"


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
