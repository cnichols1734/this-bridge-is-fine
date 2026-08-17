from __future__ import annotations

import json
from pathlib import Path

import requests
from flask import Flask, abort, jsonify, request, send_from_directory
from sqlalchemy import func, text
from sqlalchemy.orm import Session

from backend.config import Config
from backend.db import get_session, init_db
from backend.ingest import NBI_STATE_CODES
from backend.explain import METHODOLOGY, rating_plain
from backend.file_payload import file_blocks
from backend.lookups import CONDITION_WORDS, band_label, condition_word, scour_label
from backend.models import Bridge, BridgeHistory, IngestRun, IngestStateProgress
from backend.route import (
    ROUTE_BRIDGES_SQL,
    RouteError,
    ensure_included,
    fetch_osrm_route,
    filter_on_drive,
    parse_lonlat,
    pick_worst_on_drive,
    route_summary,
    select_route_bridges,
)
from backend.scoring import derive, publicize_text, record_from_bridge, score_band

def _static_dir() -> Path:
    packaged = Path(__file__).resolve().parent / "static"
    if (packaged / "index.html").exists():
        return packaged
    vite = Path(__file__).resolve().parent.parent / "frontend" / "dist"
    return vite if (vite / "index.html").exists() else packaged


STATIC_DIR = _static_dir()


def _session() -> Session:
    return get_session()


def _parse_bbox(raw: str | None):
    if not raw:
        return None
    parts = [p.strip() for p in raw.split(",")]
    if len(parts) != 4:
        return None
    try:
        west, south, east, north = (float(p) for p in parts)
    except ValueError:
        return None
    if west >= east or south >= north:
        return None
    return west, south, east, north


def _bridge_id(bridge: Bridge) -> str:
    return f"{bridge.state_code}-{bridge.structure_number}"


def _public_score(stored: int | None) -> int:
    """Public Bridge Score. Stored unease_score is already higher-is-better."""
    return int(stored or 0)


def _iso_date(value):
    if value is None:
        return None
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def _list_item(
    bridge: Bridge,
    distance_m: float | None = None,
    along: float | None = None,
) -> dict:
    item = {
        "id": _bridge_id(bridge),
        "state": bridge.state_code,
        "structure_number": bridge.structure_number,
        "lat": bridge.lat,
        "lng": bridge.lng,
        "condition": bridge.bridge_condition,
        "condition_label": band_label(bridge.bridge_condition),
        "lowest": bridge.lowest_rating,
        "score": _public_score(bridge.unease_score),
        "score_band": score_band(_public_score(bridge.unease_score)),
        "status": bridge.status_code,
        "status_label": bridge.status_label,
        "headline": publicize_text(bridge.headline),
        "facility_carried": bridge.facility_carried,
        "feature_crossed": bridge.feature_crossed,
        "adt": bridge.adt,
        "adt_suspect": bridge.adt_suspect,
        "year_built": bridge.year_built,
        "why": publicize_text(bridge.why),
    }
    if distance_m is not None:
        item["distance_km"] = round(distance_m / 1000.0, 2)
    if along is not None:
        item["along"] = round(float(along), 5)
    return item


def _rating_payload(code) -> dict:
    value = _rating_or_none(code)
    return {
        "code": code,
        "value": value,
        "word": condition_word(code),
        "plain": rating_plain(value) if value is not None else None,
    }


def _history_rows(db: Session, bridge: Bridge) -> list[dict]:
    rows = (
        db.query(BridgeHistory)
        .filter(
            BridgeHistory.state_code == bridge.state_code,
            BridgeHistory.structure_number == bridge.structure_number,
        )
        .order_by(BridgeHistory.nbi_year.asc())
        .all()
    )
    return [
        {
            "nbi_year": row.nbi_year,
            "lowest_rating": row.lowest_rating,
            "deck": row.deck,
            "superstructure": row.superstructure,
            "substructure": row.substructure,
            "culvert": row.culvert,
        }
        for row in rows
    ]


def _detail(bridge: Bridge, db: Session | None = None) -> dict:
    item = _list_item(bridge)
    explained = derive(record_from_bridge(bridge))
    item.update(
        {
            "location": bridge.location_text,
            "deck": bridge.deck,
            "superstructure": bridge.superstructure,
            "substructure": bridge.substructure,
            "culvert": bridge.culvert,
            "ratings": {
                "deck": _rating_payload(bridge.deck),
                "superstructure": _rating_payload(bridge.superstructure),
                "substructure": _rating_payload(bridge.substructure),
                "culvert": _rating_payload(bridge.culvert),
            },
            "worst_component": bridge.worst_component,
            "structure_type": bridge.structure_type,
            "year_reconstructed": bridge.year_reconstructed,
            "age_years": explained.get("age_years") if explained.get("age_years") is not None else bridge.age_years,
            "inspect_date": _iso_date(explained.get("inspect_date") or bridge.inspect_date),
            "inspect_freq_months": explained.get("inspect_freq_months")
            if explained.get("inspect_freq_months") is not None
            else bridge.inspect_freq_months,
            "inspect_due_on": _iso_date(explained.get("inspect_due_on")),
            "inspect_months_past_due": explained.get("inspect_months_past_due"),
            "inspect_overdue": bool(explained.get("inspect_overdue")),
            "fracture_critical": bridge.fracture_critical,
            "scour": explained.get("scour") or bridge.scour,
            "scour_label": scour_label(explained.get("scour") or bridge.scour),
            "scour_critical": bool(explained.get("scour_critical")),
            "is_culvert": bridge.is_culvert,
            "nbi_year": bridge.nbi_year,
            "scale": CONDITION_WORDS,
            "score": explained["score"],
            "score_band": explained["score_band"],
            "score_breakdown": explained.get("score_breakdown"),
            "summary": explained.get("summary"),
            "summary_paragraphs": explained.get("summary_paragraphs") or [],
            "explanations": explained.get("explanations") or [],
            "methodology": explained.get("methodology") or METHODOLOGY,
            "headline": publicize_text(explained.get("headline") or bridge.headline),
            "why": publicize_text(explained.get("why") or bridge.why),
        }
    )
    history = _history_rows(db, bridge) if db is not None else []
    item.update(file_blocks(bridge, history))
    return item


def _rating_or_none(value):
    if value in (None, "", "N", "n"):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _latest_ingest(db: Session) -> IngestRun | None:
    return (
        db.query(IngestRun)
        .filter(IngestRun.status == "ok")
        .order_by(IngestRun.finished_at.desc())
        .first()
    )


def _active_ingest(db: Session) -> IngestRun | None:
    # Finished error rows are history. Showing them as active made a
    # deadlock look like a live ingest long after Postgres aborted it.
    return (
        db.query(IngestRun)
        .filter(IngestRun.status == "running")
        .order_by(IngestRun.started_at.desc())
        .first()
    )


def _run_payload(run: IngestRun | None) -> dict | None:
    if run is None:
        return None
    return {
        "id": run.id,
        "status": run.status,
        "started_at": run.started_at.isoformat() if run.started_at else None,
        "finished_at": run.finished_at.isoformat() if run.finished_at else None,
        "rows_upserted": run.rows_upserted,
        "rows_skipped": run.rows_skipped,
        "pages": run.pages,
        "source_date": run.source_date,
        "checkpoint": run.checkpoint,
        "checkpoint_offset": run.checkpoint_offset or 0,
        "error": run.error,
    }


def _bbox_filter(query, bbox):
    west, south, east, north = bbox
    return query.filter(
        Bridge.lng >= west,
        Bridge.lng <= east,
        Bridge.lat >= south,
        Bridge.lat <= north,
    )


def _map_mode(zoom: float) -> str:
    """City stays mixed. State fills Poor first. Continental is Poor only."""
    if zoom >= Config.MIN_MAP_ZOOM:
        return "mixed"
    if zoom < Config.CONTINENTAL_MAP_ZOOM:
        return "poor_only"
    return "poor_first"


def _fetch_map_bridges(
    db: Session,
    bbox,
    *,
    condition: str | None = None,
    exclude_condition: str | None = None,
    limit: int,
):
    """Bbox + optional condition + limit. Do not load the national table."""
    query = _bbox_filter(db.query(Bridge), bbox)
    if condition is not None:
        query = query.filter(Bridge.bridge_condition == condition)
    if exclude_condition is not None:
        query = query.filter(Bridge.bridge_condition != exclude_condition)
    return query.order_by(Bridge.unease_score.asc()).limit(limit).all()


def _query_viewport_bridges(db: Session, bbox, zoom: float, cap: int):
    """Return (rows, capped) for the map overlay."""
    mode = _map_mode(zoom)
    if mode == "mixed":
        rows = _fetch_map_bridges(db, bbox, limit=cap + 1)
        return rows[:cap], len(rows) > cap

    poor = _fetch_map_bridges(db, bbox, condition="P", limit=cap + 1)
    if mode == "poor_only" or len(poor) >= cap:
        return poor[:cap], len(poor) > cap

    remaining = cap - len(poor)
    others = _fetch_map_bridges(
        db, bbox, exclude_condition="P", limit=remaining + 1
    )
    return poor + others[:remaining], len(others) > remaining


def _map_feature(bridge: Bridge) -> dict:
    return {
        "type": "Feature",
        "id": _bridge_id(bridge),
        "geometry": {
            "type": "Point",
            "coordinates": [bridge.lng, bridge.lat],
        },
        "properties": {
            "id": _bridge_id(bridge),
            "condition": bridge.bridge_condition,
            "lowest": bridge.lowest_rating,
            "score": _public_score(bridge.unease_score),
            "status": bridge.status_code,
        },
    }


def _radius_meters(radius_km: float, minimum_km: float, maximum_km: float) -> float:
    """Clamp a kilometer radius, then convert. Do not clamp after converting."""
    return max(minimum_km, min(float(radius_km), maximum_km)) * 1000.0


def _fetch_route_bridges(db: Session, geometry: dict, meters: float):
    """Bridges within `meters` of the route line, with distance and along-route."""
    rows = db.execute(
        text(ROUTE_BRIDGES_SQL),
        {"geojson": json.dumps(geometry), "meters": meters},
    ).all()
    if not rows:
        return []
    by_id = {
        bridge.id: bridge
        for bridge in db.query(Bridge).filter(Bridge.id.in_([row.id for row in rows])).all()
    }
    matched = []
    for row in rows:
        bridge = by_id.get(row.id)
        if bridge is None:
            continue
        bridge.along = float(row.along) if row.along is not None else 0.0
        matched.append((bridge, float(row.dist) if row.dist is not None else 0.0))
    return matched


def create_app() -> Flask:
    app = Flask(__name__, static_folder=str(STATIC_DIR), static_url_path="/static")

    @app.errorhandler(400)
    def bad_request(err):
        return jsonify({"error": err.description or "bad request"}), 400

    @app.get("/api/health")
    def health():
        db = _session()
        try:
            db.execute(text("SELECT 1"))
            ingest = _latest_ingest(db)
            active = _active_ingest(db)
            return jsonify(
                {
                    "ok": True,
                    "database": "up",
                    "last_ingest": ingest.finished_at.isoformat() if ingest and ingest.finished_at else None,
                    "ingest_status": ingest.status if ingest else "empty",
                    "active_ingest": active.status if active else None,
                }
            )
        except Exception as exc:  # noqa: BLE001
            return jsonify({"ok": False, "database": "down", "error": str(exc)}), 503
        finally:
            db.close()

    @app.get("/api/geocode")
    def geocode():
        query = (request.args.get("q") or "").strip()
        if len(query) < 2:
            abort(400, "q required")
        params = {"q": query, "limit": 8, "lang": "en"}
        try:
            params["lat"] = float(request.args["lat"])
            params["lon"] = float(request.args["lng"])
        except (KeyError, TypeError, ValueError):
            pass
        try:
            response = requests.get(
                "https://photon.komoot.io/api/",
                params=params,
                headers={"User-Agent": "ThisBridgeIsFine/1.0 (civic inventory)"},
                timeout=8,
            )
            response.raise_for_status()
            payload = response.json()
        except requests.RequestException:
            abort(502, "search unavailable")
        allowed = {"US", "PR", "GU", "VI", "AS", "MP"}
        results = []
        for feature in payload.get("features") or []:
            props = feature.get("properties") or {}
            country = (props.get("countrycode") or "").upper()
            if country and country not in allowed:
                continue
            coords = (feature.get("geometry") or {}).get("coordinates") or []
            if len(coords) < 2:
                continue
            lng, lat = float(coords[0]), float(coords[1])
            name = props.get("name") or props.get("street") or props.get("postcode")
            if not name:
                continue
            city = props.get("city") or props.get("county")
            state = props.get("state")
            postcode = props.get("postcode")
            bits = [name]
            if city and city != name:
                bits.append(city)
            if state:
                bits.append(state)
            if postcode and postcode != name:
                bits.append(postcode)
            results.append(
                {
                    "label": ", ".join(bits),
                    "lat": lat,
                    "lng": lng,
                    "kind": props.get("osm_value") or props.get("type") or "place",
                }
            )
            if len(results) >= 6:
                break
        return jsonify({"results": results})

    @app.get("/api/meta")
    def meta():
        db = _session()
        try:
            total = db.query(func.count(Bridge.id)).scalar() or 0
            poor = (
                db.query(func.count(Bridge.id))
                .filter(Bridge.bridge_condition == "P")
                .scalar()
                or 0
            )
            fair = (
                db.query(func.count(Bridge.id))
                .filter(Bridge.bridge_condition == "F")
                .scalar()
                or 0
            )
            good = (
                db.query(func.count(Bridge.id))
                .filter(Bridge.bridge_condition == "G")
                .scalar()
                or 0
            )
            unknown = (
                db.query(func.count(Bridge.id))
                .filter(
                    (Bridge.bridge_condition.is_(None))
                    | (Bridge.bridge_condition == "")
                )
                .scalar()
                or 0
            )
            states_present = (
                db.query(func.count(func.distinct(Bridge.state_code))).scalar() or 0
            )
            ingest = _latest_ingest(db)
            return jsonify(
                {
                    "total": total,
                    "good": good,
                    "fair": fair,
                    "poor": poor,
                    "unknown_condition": unknown,
                    "states_present": states_present,
                    "states_expected": len(NBI_STATE_CODES),
                    "snapshot": ingest.source_date if ingest else None,
                    "ingested_at": ingest.finished_at.isoformat()
                    if ingest and ingest.finished_at
                    else None,
                }
            )
        finally:
            db.close()

    @app.get("/api/ingest")
    def ingest_status():
        """National coverage and resume checkpoints. Data plane, not UI."""
        db = _session()
        try:
            total = db.query(func.count(Bridge.id)).scalar() or 0
            states = (
                db.query(Bridge.state_code, func.count(Bridge.id))
                .group_by(Bridge.state_code)
                .order_by(Bridge.state_code)
                .all()
            )
            present = {code for code, _count in states}
            missing = [code for code in NBI_STATE_CODES if code not in present]
            last_ok = _latest_ingest(db)
            active = _active_ingest(db)
            progress_rows = []
            if active is not None:
                progress_rows = (
                    db.query(IngestStateProgress)
                    .filter(IngestStateProgress.run_id == active.id)
                    .order_by(IngestStateProgress.id)
                    .all()
                )
            return jsonify(
                {
                    "total": total,
                    "states_present": len(states),
                    "states_expected": len(NBI_STATE_CODES),
                    "missing_states": missing,
                    "states": [
                        {"state": code, "count": int(count)} for code, count in states
                    ],
                    "last_ok_run": _run_payload(last_ok),
                    "active_run": _run_payload(active),
                    "progress": [
                        {
                            "state": row.state_code,
                            "query": row.query_key,
                            "status": row.status,
                            "expected": row.expected_count,
                            "offset": row.page_offset,
                            "upserted": row.rows_upserted,
                            "skipped": row.rows_skipped,
                            "pages": row.pages,
                            "error": row.error,
                        }
                        for row in progress_rows
                    ],
                }
            )
        finally:
            db.close()

    @app.get("/api/bridges")
    def bridges_bbox():
        bbox = _parse_bbox(request.args.get("bbox"))
        if not bbox:
            abort(400, "bbox=west,south,east,north is required")
        try:
            zoom = float(request.args.get("zoom", 11))
        except ValueError:
            abort(400, "zoom must be a number")
        db = _session()
        try:
            rows, capped = _query_viewport_bridges(
                db, bbox, zoom, Config.MAP_FEATURE_CAP
            )
            features = [_map_feature(bridge) for bridge in rows]
            return jsonify(
                {
                    "type": "FeatureCollection",
                    "features": features,
                    "capped": capped,
                    "count": len(features),
                }
            )
        finally:
            db.close()

    @app.get("/api/bridges/list")
    def bridges_list():
        bbox = _parse_bbox(request.args.get("bbox"))
        if not bbox:
            abort(400, "bbox=west,south,east,north is required")
        west, south, east, north = bbox
        clat = (south + north) / 2
        clng = (west + east) / 2
        db = _session()
        try:
            rows = db.execute(
                text(
                    """
                    SELECT id,
                           ST_Distance(
                             geog,
                             ST_SetSRID(ST_MakePoint(:lng, :lat), 4326)::geography
                           ) AS dist
                    FROM bridges
                    WHERE lng BETWEEN :west AND :east
                      AND lat BETWEEN :south AND :north
                    ORDER BY dist
                    LIMIT 60
                    """
                ),
                {
                    "west": west,
                    "south": south,
                    "east": east,
                    "north": north,
                    "lat": clat,
                    "lng": clng,
                },
            ).all()
            if not rows:
                return jsonify({"bridges": [], "count": 0})
            by_id = {
                b.id: b
                for b in db.query(Bridge).filter(Bridge.id.in_([r.id for r in rows])).all()
            }
            ordered = [(by_id[r.id], float(r.dist)) for r in rows if r.id in by_id]
            return jsonify(
                {"bridges": [_list_item(bridge, dist) for bridge, dist in ordered]}
            )
        finally:
            db.close()

    @app.get("/api/bridges/nearby")
    def nearby():
        try:
            lat = float(request.args["lat"])
            lng = float(request.args["lng"])
            radius_km = float(request.args.get("radius_km", Config.DEFAULT_NEARBY_KM))
        except (KeyError, ValueError):
            abort(400, "lat, lng required")
        meters = _radius_meters(radius_km, 0.5, 80)
        db = _session()
        try:
            rows = db.execute(
                text(
                    """
                    SELECT id,
                           ST_Distance(
                             geog,
                             ST_SetSRID(ST_MakePoint(:lng, :lat), 4326)::geography
                           ) AS dist
                    FROM bridges
                    WHERE ST_DWithin(
                      geog,
                      ST_SetSRID(ST_MakePoint(:lng, :lat), 4326)::geography,
                      :meters
                    )
                    ORDER BY dist
                    LIMIT 80
                    """
                ),
                {"lat": lat, "lng": lng, "meters": meters},
            ).all()
            if not rows:
                return jsonify({"bridges": [], "count": 0})
            by_id = {
                b.id: b
                for b in db.query(Bridge).filter(Bridge.id.in_([r.id for r in rows])).all()
            }
            ordered = [(by_id[r.id], float(r.dist)) for r in rows if r.id in by_id]
            return jsonify(
                {
                    "bridges": [_list_item(bridge, dist) for bridge, dist in ordered],
                    "count": len(ordered),
                }
            )
        finally:
            db.close()

    @app.get("/api/worst")
    def worst():
        bbox = _parse_bbox(request.args.get("bbox"))
        limit = min(int(request.args.get("limit", Config.WORST_LIMIT)), 25)
        db = _session()
        try:
            if bbox:
                rows = (
                    _bbox_filter(db.query(Bridge), bbox)
                    .order_by(Bridge.unease_score.asc(), Bridge.adt.desc())
                    .limit(limit)
                    .all()
                )
            else:
                try:
                    lat = float(request.args["lat"])
                    lng = float(request.args["lng"])
                    radius_km = float(
                        request.args.get("radius_km", Config.DEFAULT_WORST_KM)
                    )
                except (KeyError, ValueError):
                    abort(400, "bbox or lat/lng required")
                meters = _radius_meters(radius_km, 1.0, 80)
                ids = db.execute(
                    text(
                        """
                        SELECT id FROM bridges
                        WHERE ST_DWithin(
                          geog,
                          ST_SetSRID(ST_MakePoint(:lng, :lat), 4326)::geography,
                          :meters
                        )
                        ORDER BY unease_score ASC, adt DESC NULLS LAST
                        LIMIT :limit
                        """
                    ),
                    {"lat": lat, "lng": lng, "meters": meters, "limit": limit},
                ).all()
                by_id = {
                    b.id: b
                    for b in db.query(Bridge)
                    .filter(Bridge.id.in_([r.id for r in ids]))
                    .all()
                }
                rows = [by_id[r.id] for r in ids if r.id in by_id]
            return jsonify({"bridges": [_list_item(b) for b in rows]})
        finally:
            db.close()


    @app.get("/api/stats")
    def stats():
        bbox = _parse_bbox(request.args.get("bbox"))
        if not bbox:
            abort(400, "bbox=west,south,east,north is required")
        db = _session()
        try:
            query = _bbox_filter(db.query(Bridge), bbox)
            total = query.count()
            poor = query.filter(Bridge.bridge_condition == "P").count()
            crossings = (
                query.filter(
                    Bridge.bridge_condition == "P",
                    Bridge.adt_suspect.is_(False),
                )
                .with_entities(func.coalesce(func.sum(Bridge.adt), 0))
                .scalar()
            )
            return jsonify(
                {
                    "total": total,
                    "poor": poor,
                    "poor_pct": round((poor / total) * 100, 1) if total else 0,
                    "daily_crossings_on_poor": int(crossings or 0),
                }
            )
        finally:
            db.close()

    @app.get("/api/drive")
    def drive():
        start = parse_lonlat(request.args.get("from"))
        end = parse_lonlat(request.args.get("to"))
        if not start or not end:
            abort(400, "from=lng,lat and to=lng,lat are required")
        if start == end:
            abort(400, "start and end must be different points")
        try:
            route = fetch_osrm_route(start, end)
        except RouteError as exc:
            return jsonify({"error": exc.message}), exc.status
        db = _session()
        try:
            matched = _fetch_route_bridges(
                db, route["geometry"], float(Config.ROUTE_BUFFER_M)
            )
            candidates = [bridge for bridge, _dist in matched]
            on_drive = filter_on_drive(candidates, route.get("roads") or [])
            summary = route_summary(on_drive)
            worst_rows = pick_worst_on_drive(on_drive, 3)
            listed, capped = select_route_bridges(on_drive, Config.ROUTE_LIST_CAP)
            listed = ensure_included(listed, worst_rows)
            return jsonify(
                {
                    "route": {
                        "geometry": route["geometry"],
                        "distance_m": route["distance_m"],
                        "duration_s": route["duration_s"],
                        "steps": route.get("steps") or [],
                    },
                    "summary": {
                        **summary,
                        "listed": len(listed),
                        "capped": capped,
                    },
                    "bridges": [
                        _list_item(bridge, along=getattr(bridge, "along", None))
                        for bridge in listed
                    ],
                    "worst": [
                        _list_item(bridge, along=getattr(bridge, "along", None))
                        for bridge in worst_rows
                    ],
                }
            )
        finally:
            db.close()

    @app.get("/api/bridges/<state>/<path:structure_number>")
    def bridge_detail(state: str, structure_number: str):
        db = _session()
        try:
            bridge = (
                db.query(Bridge)
                .filter(
                    Bridge.state_code == state.zfill(2)[-2:],
                    Bridge.structure_number == structure_number,
                )
                .one_or_none()
            )
            if bridge is None:
                abort(404)
            return jsonify(_detail(bridge, db))
        finally:
            db.close()

    @app.errorhandler(404)
    def not_found(err):
        if request.path.startswith("/api/"):
            return jsonify({"error": "not found"}), 404
        return _spa_index()

    def _spa_index():
        index = STATIC_DIR / "index.html"
        if index.exists():
            return send_from_directory(STATIC_DIR, "index.html")
        return jsonify({"ok": True, "service": "this-bridge-is-fine"}), 200

    @app.get("/")
    def root():
        return _spa_index()

    @app.get("/<path:path>")
    def spa(path: str):
        if path.startswith("api/"):
            abort(404)
        target = STATIC_DIR / path
        if path and target.exists() and target.is_file():
            return send_from_directory(STATIC_DIR, path)
        return _spa_index()

    return app


def boot() -> Flask:
    try:
        init_db()
    except Exception:
        # Fresh container may start before PostGIS is reachable; /api/health reports it.
        pass
    return create_app()
