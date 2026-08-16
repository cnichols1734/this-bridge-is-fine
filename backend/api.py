from __future__ import annotations

from pathlib import Path

import requests
from flask import Flask, abort, jsonify, request, send_from_directory
from sqlalchemy import func, text
from sqlalchemy.orm import Session

from backend.config import Config
from backend.db import get_session, init_db
from backend.ingest import NBI_STATE_CODES
from backend.lookups import CONDITION_WORDS, band_label, condition_word
from backend.models import Bridge, IngestRun, IngestStateProgress
from backend.scoring import publicize_text

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


def _public_score(unease: int | None) -> int:
    """Public score runs the same way as inspector ratings: higher is better."""
    return 100 - int(unease or 0)


def _list_item(bridge: Bridge, distance_m: float | None = None) -> dict:
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
    return item


def _detail(bridge: Bridge) -> dict:
    item = _list_item(bridge)
    item.update(
        {
            "location": bridge.location_text,
            "deck": bridge.deck,
            "superstructure": bridge.superstructure,
            "substructure": bridge.substructure,
            "culvert": bridge.culvert,
            "ratings": {
                "deck": {
                    "code": bridge.deck,
                    "value": _rating_or_none(bridge.deck),
                    "word": condition_word(bridge.deck),
                },
                "superstructure": {
                    "code": bridge.superstructure,
                    "value": _rating_or_none(bridge.superstructure),
                    "word": condition_word(bridge.superstructure),
                },
                "substructure": {
                    "code": bridge.substructure,
                    "value": _rating_or_none(bridge.substructure),
                    "word": condition_word(bridge.substructure),
                },
                "culvert": {
                    "code": bridge.culvert,
                    "value": _rating_or_none(bridge.culvert),
                    "word": condition_word(bridge.culvert),
                },
            },
            "worst_component": bridge.worst_component,
            "structure_type": bridge.structure_type,
            "year_reconstructed": bridge.year_reconstructed,
            "age_years": bridge.age_years,
            "inspect_date": bridge.inspect_date.isoformat() if bridge.inspect_date else None,
            "inspect_freq_months": bridge.inspect_freq_months,
            "inspect_overdue": bridge.inspect_overdue,
            "fracture_critical": bridge.fracture_critical,
            "scour_critical": bridge.scour_critical,
            "is_culvert": bridge.is_culvert,
            "nbi_year": "2025",
            "scale": CONDITION_WORDS,
        }
    )
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
    return (
        db.query(IngestRun)
        .filter(IngestRun.status.in_(("running", "error")))
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


def _radius_meters(radius_km: float, minimum_km: float, maximum_km: float) -> float:
    """Clamp a kilometer radius, then convert. Do not clamp after converting."""
    return max(minimum_km, min(float(radius_km), maximum_km)) * 1000.0


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
        if zoom < Config.MIN_MAP_ZOOM:
            return jsonify(
                {
                    "type": "FeatureCollection",
                    "features": [],
                    "hint": "Zoom in to city scale to see structures.",
                    "capped": False,
                }
            )
        db = _session()
        try:
            rows = (
                _bbox_filter(db.query(Bridge), bbox)
                .order_by(Bridge.unease_score.desc())
                .limit(Config.MAP_FEATURE_CAP + 1)
                .all()
            )
            capped = len(rows) > Config.MAP_FEATURE_CAP
            rows = rows[: Config.MAP_FEATURE_CAP]
            features = [
                {
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
                for bridge in rows
            ]
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
                    .order_by(Bridge.unease_score.desc(), Bridge.adt.desc())
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
                        ORDER BY unease_score DESC, adt DESC NULLS LAST
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
            return jsonify(_detail(bridge))
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
