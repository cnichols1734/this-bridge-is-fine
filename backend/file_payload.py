"""Detail-file blocks. Formatted NBI extras for the bridge file."""

from __future__ import annotations

from typing import Any

from backend.explain import dimensions_note, load_ratings_paragraph, structure_intro
from backend.history import condition_trend
from backend.lookups import (
    agency_label,
    design_label,
    format_area_m2,
    format_detour_km,
    format_length_m,
    format_tons,
    historic_label,
    material_label,
    route_prefix_label,
    scour_label,
    short_tons,
    structure_phrase,
    toll_label,
)


def _has_values(block: dict[str, Any], keys: tuple[str, ...]) -> bool:
    return any(block.get(key) not in (None, "", "—") for key in keys)


def file_blocks(bridge: Any, history_rows: list[dict] | None = None) -> dict[str, Any]:
    phrase = bridge.structure_type or structure_phrase(
        getattr(bridge, "material_code", None), getattr(bridge, "design_code", None)
    )
    owner = agency_label(getattr(bridge, "owner_code", None))
    maintainer = agency_label(getattr(bridge, "maintenance_code", None))
    material = material_label(getattr(bridge, "material_code", None))
    design = design_label(getattr(bridge, "design_code", None))
    if material:
        material = material[:1].upper() + material[1:]
    if design:
        design = design[:1].upper() + design[1:]

    length_label = format_length_m(getattr(bridge, "structure_length_m", None))
    span_label = format_length_m(getattr(bridge, "max_span_m", None))
    width_label = format_length_m(getattr(bridge, "deck_width_m", None))
    area_label = format_area_m2(getattr(bridge, "deck_area_m2", None))

    operating = getattr(bridge, "operating_rating", None)
    inventory = getattr(bridge, "inventory_rating", None)
    operating_label = format_tons(operating)
    inventory_label = format_tons(inventory)
    posted = (getattr(bridge, "status_code", None) or "").upper() in {"P", "B", "R"}

    structure = {
        "material": material,
        "design": design,
        "phrase": phrase,
        "owner": owner,
        "maintainer": maintainer,
        "year_built": getattr(bridge, "year_built", None),
        "year_reconstructed": getattr(bridge, "year_reconstructed", None),
        "intro": structure_intro(phrase, maintainer, owner),
    }
    dimensions = {
        "length_m": getattr(bridge, "structure_length_m", None),
        "length_label": length_label,
        "max_span_m": getattr(bridge, "max_span_m", None),
        "max_span_label": span_label,
        "deck_width_m": getattr(bridge, "deck_width_m", None),
        "deck_width_label": width_label,
        "deck_area_m2": getattr(bridge, "deck_area_m2", None),
        "deck_area_label": area_label,
        "note": dimensions_note(area_label),
    }
    route_number = getattr(bridge, "route_number", None)
    classification = {
        "route_type": route_prefix_label(getattr(bridge, "route_prefix", None)),
        "route_number": route_number,
        "lanes_on": getattr(bridge, "lanes_on", None),
        "lanes_under": getattr(bridge, "lanes_under", None),
    }
    inventory_status = {
        "toll": toll_label(getattr(bridge, "toll_code", None)),
        "historic": historic_label(getattr(bridge, "history_code", None)),
        "scour": scour_label(getattr(bridge, "scour", None)),
        "detour_label": format_detour_km(getattr(bridge, "detour_km", None)),
    }
    load_ratings = {
        "operating_tons": short_tons(operating),
        "operating_label": operating_label,
        "operating_caption": "Maximum reported load for special permits",
        "inventory_tons": short_tons(inventory),
        "inventory_label": inventory_label,
        "inventory_caption": "Reported load level for everyday traffic",
        "paragraph": load_ratings_paragraph(
            operating_label, inventory_label, short_tons(operating), posted
        ),
    }
    trend = condition_trend(history_rows or [])

    return {
        "structure": structure if _has_values(structure, ("material", "design", "owner", "maintainer", "year_built", "year_reconstructed", "intro")) else None,
        "dimensions": dimensions if _has_values(dimensions, ("length_label", "max_span_label", "deck_width_label", "deck_area_label")) else None,
        "classification": classification if _has_values(classification, ("route_type", "route_number", "lanes_on", "lanes_under")) else None,
        "inventory_status": inventory_status if _has_values(inventory_status, ("toll", "historic", "scour", "detour_label")) else None,
        "load_ratings": load_ratings if operating_label or inventory_label else None,
        "condition_trend": trend,
        "glance_length": length_label,
    }
