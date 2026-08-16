"""Drive overview: OSRM geometry plus bridges you actually drive over.

Open-source routing only. The browser never talks to the router.
Default is the public OSRM demo; set OSRM_BASE_URL to point at your own.

A nearby NBI point is not enough. Overpasses you go under sit in the same
buffer as the span you ride. The route's road names (OSRM steps) are matched
to `facility_carried` — the road ON the structure. `feature_crossed` is what
you pass under; a match there is not "on the drive."
"""

from __future__ import annotations

import re
from typing import Any

import requests

from backend.config import Config


def parse_lonlat(raw: str | None) -> tuple[float, float] | None:
    """Parse 'lng,lat'. Same axis order as bbox."""
    if not raw:
        return None
    parts = [p.strip() for p in raw.split(",")]
    if len(parts) != 2:
        return None
    try:
        lng, lat = float(parts[0]), float(parts[1])
    except ValueError:
        return None
    if not (-180 <= lng <= 180 and -90 <= lat <= 90):
        return None
    return lng, lat


def route_summary(rows: list) -> dict:
    """Full counts for every structure in the buffer, including those not listed."""
    total = len(rows)
    poor = sum(1 for row in rows if getattr(row, "bridge_condition", None) == "P")
    fair = sum(1 for row in rows if getattr(row, "bridge_condition", None) == "F")
    good = sum(1 for row in rows if getattr(row, "bridge_condition", None) == "G")
    return {
        "bridges": total,
        "poor": poor,
        "fair": fair,
        "good": good,
        "unknown": total - poor - fair - good,
    }


def select_route_bridges(rows: list, cap: int) -> tuple[list, bool]:
    """List Poor first, then others. Never drop Poor to stay under the cap.

    Others fill remaining slots by position along the drive, then unease.
    Summary counts stay complete even when the list is truncated.
    """
    poor = [row for row in rows if getattr(row, "bridge_condition", None) == "P"]
    others = [row for row in rows if getattr(row, "bridge_condition", None) != "P"]
    poor.sort(key=lambda row: (getattr(row, "along", 0) or 0, -(getattr(row, "unease_score", 0) or 0)))
    others.sort(key=lambda row: (getattr(row, "along", 0) or 0, -(getattr(row, "unease_score", 0) or 0)))
    if len(poor) >= cap:
        return poor, len(others) > 0
    remaining = cap - len(poor)
    return poor + others[:remaining], len(others) > remaining


def pick_worst_on_drive(rows: list, n: int = 3) -> list:
    """Official Poor first, then lowest public score (highest unease), then lowest rating."""

    def sort_key(row):
        poor = 0 if getattr(row, "bridge_condition", None) == "P" else 1
        unease = int(getattr(row, "unease_score", 0) or 0)
        raw = getattr(row, "lowest_rating", None)
        try:
            lowest = int(raw)
        except (TypeError, ValueError):
            lowest = 99
        return (poor, -unease, lowest)

    return sorted(rows, key=sort_key)[:n]


def ensure_included(listed: list, extra: list) -> list:
    seen = {getattr(row, "id", id(row)) for row in listed}
    out = list(listed)
    for row in extra:
        key = getattr(row, "id", id(row))
        if key in seen:
            continue
        out.append(row)
        seen.add(key)
    return out


_NOISE = {
    "NB",
    "SB",
    "EB",
    "WB",
    "NBL",
    "SBL",
    "EBL",
    "WBL",
    "NORTHBOUND",
    "SOUTHBOUND",
    "EASTBOUND",
    "WESTBOUND",
    "TO",
    "FROM",
    "RAMP",
    "CONN",
    "CONNECTOR",
    "JCT",
    "JCTN",
    "THE",
    "AND",
    "OF",
    "AT",
}

_DIR = {
    "NORTH": "N",
    "SOUTH": "S",
    "EAST": "E",
    "WEST": "W",
    "NORTHEAST": "NE",
    "NORTHWEST": "NW",
    "SOUTHEAST": "SE",
    "SOUTHWEST": "SW",
}

_SUFFIX = {
    "STREET": "ST",
    "STR": "ST",
    "AVENUE": "AVE",
    "AV": "AVE",
    "DRIVE": "DR",
    "ROAD": "RD",
    "BOULEVARD": "BLVD",
    "PARKWAY": "PKWY",
    "PKY": "PKWY",
    "HIGHWAY": "HWY",
    "LANE": "LN",
    "PLACE": "PL",
    "COURT": "CT",
    "CIRCLE": "CIR",
    "TRAIL": "TRL",
    "TERRACE": "TER",
    "EXPRESSWAY": "EXPY",
    "FREEWAY": "FWY",
    "TURNPIKE": "TPKE",
}

_HIGHWAY_RES = (
    (re.compile(r"\bINTERSTATE\s+HIGHWAY\s+(\d+[A-Z]?)\b"), r" I\1 "),
    (re.compile(r"\bINTERSTATE\s+(\d+[A-Z]?)\b"), r" I\1 "),
    (re.compile(r"\bIH\s*(\d+[A-Z]?)\b"), r" I\1 "),
    (re.compile(r"\bI[\s\-]*(\d+[A-Z]?)\b"), r" I\1 "),
    (re.compile(r"\bU\.?\s*S\.?\s*(?:HIGHWAY|HWY|RTE|ROUTE)?\s*(\d+[A-Z]?)\b"), r" US\1 "),
    (re.compile(r"\bUS\s*(?:HIGHWAY|HWY|RTE|ROUTE)\s*(\d+[A-Z]?)\b"), r" US\1 "),
    (re.compile(r"\bUS\s*(\d+[A-Z]?)\b"), r" US\1 "),
    (re.compile(r"\bSTATE\s+(?:HIGHWAY|HWY|ROUTE|RTE|ROAD)\s+(\d+[A-Z]?)\b"), r" SH\1 "),
    (re.compile(r"\bSH\s*(\d+[A-Z]?)\b"), r" SH\1 "),
    (re.compile(r"\bTX\s+(\d+[A-Z]?)\b"), r" SH\1 "),
    (re.compile(r"\bFARM\s+TO\s+MARKET(?:\s+ROAD)?\s+(\d+)\b"), r" FM\1 "),
    (re.compile(r"\bFM\s*(\d+)\b"), r" FM\1 "),
    (re.compile(r"\bRANCH\s+(?:TO\s+MARKET|ROAD)\s+(\d+)\b"), r" RM\1 "),
    (re.compile(r"\bRM\s*(\d+)\b"), r" RM\1 "),
    (re.compile(r"\bBELTWAY\s+(\d+)\b"), r" BELTWAY\1 "),
    (re.compile(r"\bSPUR\s+(\d+)\b"), r" SPUR\1 "),
    (re.compile(r"\bLOOP\s+(\d+)\b"), r" LOOP\1 "),
    (re.compile(r"\bSTATE\s+ROAD\s+(\d+[A-Z]?)\b"), r" SR\1 "),
    (re.compile(r"\bSR\s*(\d+[A-Z]?)\b"), r" SR\1 "),
    (re.compile(r"\bCOUNTY\s+(?:ROAD|RD|ROUTE|RTE)\s+(\d+)\b"), r" CR\1 "),
    (re.compile(r"\bCR\s*(\d+)\b"), r" CR\1 "),
)

_CODE_RE = re.compile(
    r"^(I|US|SH|FM|RM|SR|CR|BUS|SPUR|LOOP|BELTWAY)(\d+[A-Z]?)$"
)


def road_keys(name: str | None) -> set[str]:
    """Comparable tokens: I45, US59, ALABAMA ST. Empty if the name is noise."""
    if not name or not str(name).strip():
        return set()
    text = re.sub(r"[^A-Z0-9]+", " ", str(name).upper())
    text = f" {text} "
    for pat, repl in _HIGHWAY_RES:
        text = pat.sub(repl, text)
    keys: set[str] = set()
    words: list[str] = []
    for tok in text.split():
        if tok in _NOISE:
            continue
        tok = _DIR.get(tok, tok)
        tok = _SUFFIX.get(tok, tok)
        if _CODE_RE.match(tok):
            keys.add(tok)
            continue
        words.append(tok)
    if words:
        keys.add(" ".join(words))
        if words[0] in {"N", "S", "E", "W", "NE", "NW", "SE", "SW"} and len(words) > 1:
            keys.add(" ".join(words[1:]))
        if len(words) >= 2:
            keys.add(" ".join(words[-2:]))
    return {key for key in keys if len(key) >= 2}


def roads_match(name: str | None, route_roads: list[str]) -> bool:
    keys = road_keys(name)
    if not keys:
        return False
    route_keys: set[str] = set()
    for road in route_roads:
        route_keys |= road_keys(road)
    return bool(keys & route_keys)


def collect_route_roads(osrm_route: dict) -> list[str]:
    names: list[str] = []
    for leg in osrm_route.get("legs") or []:
        for step in leg.get("steps") or []:
            if step.get("name"):
                names.append(str(step["name"]))
            raw_ref = step.get("ref") or ""
            for part in re.split(r"[;/]", str(raw_ref)):
                part = part.strip()
                if part:
                    names.append(part)
    seen: set[str] = set()
    out: list[str] = []
    for name in names:
        if name in seen:
            continue
        seen.add(name)
        out.append(name)
    return out


def extract_steps(osrm_route: dict) -> list[dict[str, Any]]:
    steps: list[dict[str, Any]] = []
    for leg in osrm_route.get("legs") or []:
        for step in leg.get("steps") or []:
            man = step.get("maneuver") or {}
            loc = man.get("location") or []
            steps.append(
                {
                    "type": man.get("type") or "continue",
                    "modifier": man.get("modifier"),
                    "name": step.get("name") or "",
                    "ref": step.get("ref") or "",
                    "distance_m": float(step.get("distance") or 0),
                    "duration_s": float(step.get("duration") or 0),
                    "location": [float(loc[0]), float(loc[1])] if len(loc) >= 2 else None,
                }
            )
    return steps


def filter_on_drive(bridges: list, route_roads: list[str]) -> list:
    """Keep structures whose facility is a road the route travels.

    If OSRM returned no usable names, keep the spatial set — there is nothing
    to match. A feature_crossed match without a facility match is going under.
    """
    usable = [road for road in route_roads if road_keys(road)]
    if not usable:
        return list(bridges)
    return [
        bridge
        for bridge in bridges
        if roads_match(getattr(bridge, "facility_carried", None), usable)
    ]


def osrm_route_url(start: tuple[float, float], end: tuple[float, float], base: str | None = None) -> str:
    origin = (base or Config.OSRM_BASE_URL).rstrip("/")
    slng, slat = start
    elng, elat = end
    return (
        f"{origin}/route/v1/driving/{slng},{slat};{elng},{elat}"
        "?overview=full&geometries=geojson&steps=true"
    )


def fetch_osrm_route(
    start: tuple[float, float],
    end: tuple[float, float],
    *,
    base: str | None = None,
    timeout: float = 20,
) -> dict[str, Any]:
    """Return {geometry, distance_m, duration_s} or raise RouteError."""
    url = osrm_route_url(start, end, base)
    try:
        response = requests.get(
            url,
            headers={"User-Agent": "ThisBridgeIsFine/1.0 (civic inventory)"},
            timeout=timeout,
        )
    except requests.RequestException as exc:
        raise RouteError("routing unavailable", status=502) from exc
    if response.status_code >= 500:
        raise RouteError("routing unavailable", status=502)
    try:
        payload = response.json()
    except ValueError as exc:
        raise RouteError("routing unavailable", status=502) from exc
    code = payload.get("code")
    if code == "NoRoute" or not payload.get("routes"):
        raise RouteError("no driving route for these points", status=404)
    if code != "Ok":
        raise RouteError("routing unavailable", status=502)
    route = payload["routes"][0]
    geometry = route.get("geometry") or {}
    if geometry.get("type") != "LineString" or not geometry.get("coordinates"):
        raise RouteError("routing unavailable", status=502)
    return {
        "geometry": {
            "type": "LineString",
            "coordinates": geometry["coordinates"],
        },
        "distance_m": float(route.get("distance") or 0),
        "duration_s": float(route.get("duration") or 0),
        "steps": extract_steps(route),
        "roads": collect_route_roads(route),
    }


class RouteError(Exception):
    def __init__(self, message: str, status: int = 502):
        super().__init__(message)
        self.message = message
        self.status = status


ROUTE_BRIDGES_SQL = """
WITH route AS (
  SELECT ST_SetSRID(ST_GeomFromGeoJSON(:geojson), 4326) AS geom
)
SELECT b.id,
       ST_Distance(b.geog, route.geom::geography) AS dist,
       ST_LineLocatePoint(
         route.geom,
         ST_SetSRID(ST_MakePoint(b.lng, b.lat), 4326)
       ) AS along
FROM bridges b, route
WHERE ST_DWithin(b.geog, route.geom::geography, :meters)
"""
