"""Drive overview: OSRM geometry plus bridges within a route buffer.

Open-source routing only. The browser never talks to the router.
Default is the public OSRM demo; set OSRM_BASE_URL to point at your own.
"""

from __future__ import annotations

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


def osrm_route_url(start: tuple[float, float], end: tuple[float, float], base: str | None = None) -> str:
    origin = (base or Config.OSRM_BASE_URL).rstrip("/")
    slng, slat = start
    elng, elat = end
    return (
        f"{origin}/route/v1/driving/{slng},{slat};{elng},{elat}"
        "?overview=full&geometries=geojson&steps=false"
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
