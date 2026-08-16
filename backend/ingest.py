"""Paginated NTAD ingest. Treat ADT as hostile. Drop junk coordinates."""

from __future__ import annotations

import argparse
import sys
import time
from datetime import datetime, timezone

import requests
from sqlalchemy import text

from backend.config import Config
from backend.db import get_session, init_db
from backend.models import IngestRun
from backend.scoring import derive

PAGE_SIZE = 2000
SLEEP_SECONDS = 0.12
MAX_RETRIES = 5
EMPTY_PAGE_RETRIES = 8

# FHWA NBI state/territory FIPS codes. National pulls walk these so a
# single empty ArcGIS page cannot halt the whole inventory at ~350k.
NBI_STATE_CODES = (
    "01",
    "02",
    "04",
    "05",
    "06",
    "08",
    "09",
    "10",
    "11",
    "12",
    "13",
    "15",
    "16",
    "17",
    "18",
    "19",
    "20",
    "21",
    "22",
    "23",
    "24",
    "25",
    "26",
    "27",
    "28",
    "29",
    "30",
    "31",
    "32",
    "33",
    "34",
    "35",
    "36",
    "37",
    "38",
    "39",
    "40",
    "41",
    "42",
    "44",
    "45",
    "46",
    "47",
    "48",
    "49",
    "50",
    "51",
    "53",
    "54",
    "55",
    "56",
    "60",
    "66",
    "69",
    "72",
    "78",
)
OUT_FIELDS = [
    "STATE_CODE_001",
    "STRUCTURE_NUMBER_008",
    "DATE",
    "LATDD",
    "LONGDD",
    "FACILITY_CARRIED_007",
    "FEATURES_DESC_006A",
    "LOCATION_009",
    "DECK_COND_058",
    "SUPERSTRUCTURE_COND_059",
    "SUBSTRUCTURE_COND_060",
    "CULVERT_COND_062",
    "LOWEST_RATING",
    "BRIDGE_CONDITION",
    "OPEN_CLOSED_POSTED_041",
    "SCOUR_CRITICAL_113",
    "FRACTURE_092A",
    "YEAR_BUILT_027",
    "YEAR_RECONSTRUCTED_106",
    "ADT_029",
    "YEAR_ADT_030",
    "DATE_OF_INSPECT_090",
    "INSPECT_FREQ_MONTHS_091",
    "FUNCTIONAL_CLASS_026",
    "STRUCTURE_KIND_043A",
    "STRUCTURE_TYPE_043B",
]

UPSERT_SQL = text(
    """
    INSERT INTO bridges (
        state_code, structure_number, nbi_year,
        lat, lng, geog,
        facility_carried, feature_crossed, location_text,
        deck, superstructure, substructure, culvert,
        lowest_rating, bridge_condition,
        status_code, status_label, scour, fracture,
        year_built, year_reconstructed, adt, adt_year,
        inspect_raw, inspect_date, inspect_freq_months,
        functional_class, material_code, design_code, structure_type,
        age_years, inspect_overdue, adt_suspect, adt_capped, is_culvert,
        unease_score, headline, why, worst_component,
        fracture_critical, scour_critical, updated_at
    ) VALUES (
        :state_code, :structure_number, :nbi_year,
        :lat, :lng, ST_SetSRID(ST_MakePoint(:lng, :lat), 4326)::geography,
        :facility_carried, :feature_crossed, :location_text,
        :deck, :superstructure, :substructure, :culvert,
        :lowest_rating, :bridge_condition,
        :status_code, :status_label, :scour, :fracture,
        :year_built, :year_reconstructed, :adt, :adt_year,
        :inspect_raw, :inspect_date, :inspect_freq_months,
        :functional_class, :material_code, :design_code, :structure_type,
        :age_years, :inspect_overdue, :adt_suspect, :adt_capped, :is_culvert,
        :unease_score, :headline, :why, :worst_component,
        :fracture_critical, :scour_critical, NOW()
    )
    ON CONFLICT (state_code, structure_number) DO UPDATE SET
        nbi_year = EXCLUDED.nbi_year,
        lat = EXCLUDED.lat,
        lng = EXCLUDED.lng,
        geog = EXCLUDED.geog,
        facility_carried = EXCLUDED.facility_carried,
        feature_crossed = EXCLUDED.feature_crossed,
        location_text = EXCLUDED.location_text,
        deck = EXCLUDED.deck,
        superstructure = EXCLUDED.superstructure,
        substructure = EXCLUDED.substructure,
        culvert = EXCLUDED.culvert,
        lowest_rating = EXCLUDED.lowest_rating,
        bridge_condition = EXCLUDED.bridge_condition,
        status_code = EXCLUDED.status_code,
        status_label = EXCLUDED.status_label,
        scour = EXCLUDED.scour,
        fracture = EXCLUDED.fracture,
        year_built = EXCLUDED.year_built,
        year_reconstructed = EXCLUDED.year_reconstructed,
        adt = EXCLUDED.adt,
        adt_year = EXCLUDED.adt_year,
        inspect_raw = EXCLUDED.inspect_raw,
        inspect_date = EXCLUDED.inspect_date,
        inspect_freq_months = EXCLUDED.inspect_freq_months,
        functional_class = EXCLUDED.functional_class,
        material_code = EXCLUDED.material_code,
        design_code = EXCLUDED.design_code,
        structure_type = EXCLUDED.structure_type,
        age_years = EXCLUDED.age_years,
        inspect_overdue = EXCLUDED.inspect_overdue,
        adt_suspect = EXCLUDED.adt_suspect,
        adt_capped = EXCLUDED.adt_capped,
        is_culvert = EXCLUDED.is_culvert,
        unease_score = EXCLUDED.unease_score,
        headline = EXCLUDED.headline,
        why = EXCLUDED.why,
        worst_component = EXCLUDED.worst_component,
        fracture_critical = EXCLUDED.fracture_critical,
        scour_critical = EXCLUDED.scour_critical,
        updated_at = NOW()
    """
)


def _clean(value):
    if value is None:
        return None
    if isinstance(value, str):
        text_value = value.strip()
        return text_value or None
    return value


def valid_point(lat, lng) -> bool:
    try:
        lat_f = float(lat)
        lng_f = float(lng)
    except (TypeError, ValueError):
        return False
    if lat_f == 0 and lng_f == 0:
        return False
    if not (14.0 <= lat_f <= 72.0):
        return False
    if not (-180.0 <= lng_f <= -60.0 or 140.0 <= lng_f <= 180.0):
        return False
    return True


def map_feature(attrs: dict) -> dict | None:
    lat = attrs.get("LATDD")
    lng = attrs.get("LONGDD")
    if not valid_point(lat, lng):
        return None
    state = _clean(attrs.get("STATE_CODE_001"))
    structure = _clean(attrs.get("STRUCTURE_NUMBER_008"))
    if not state or not structure:
        return None
    year_rebuilt = attrs.get("YEAR_RECONSTRUCTED_106")
    try:
        year_rebuilt_i = int(year_rebuilt) if year_rebuilt not in (None, "", 0, "0") else None
    except (TypeError, ValueError):
        year_rebuilt_i = None
    try:
        year_built = int(attrs["YEAR_BUILT_027"]) if attrs.get("YEAR_BUILT_027") else None
    except (TypeError, ValueError):
        year_built = None
    try:
        adt = int(attrs["ADT_029"]) if attrs.get("ADT_029") is not None else 0
    except (TypeError, ValueError):
        adt = 0
    try:
        freq = (
            int(attrs["INSPECT_FREQ_MONTHS_091"])
            if attrs.get("INSPECT_FREQ_MONTHS_091")
            else None
        )
    except (TypeError, ValueError):
        freq = None
    try:
        lowest = (
            int(attrs["LOWEST_RATING"]) if attrs.get("LOWEST_RATING") is not None else None
        )
    except (TypeError, ValueError):
        lowest = None

    raw = {
        "state_code": str(state).zfill(2)[-2:],
        "structure_number": structure,
        "nbi_year": _clean(attrs.get("DATE")),
        "lat": float(lat),
        "lng": float(lng),
        "facility_carried": _clean(attrs.get("FACILITY_CARRIED_007")),
        "feature_crossed": _clean(attrs.get("FEATURES_DESC_006A")),
        "location_text": _clean(attrs.get("LOCATION_009")),
        "deck": _clean(attrs.get("DECK_COND_058")),
        "superstructure": _clean(attrs.get("SUPERSTRUCTURE_COND_059")),
        "substructure": _clean(attrs.get("SUBSTRUCTURE_COND_060")),
        "culvert": _clean(attrs.get("CULVERT_COND_062")),
        "lowest_rating": lowest,
        "bridge_condition": _clean(attrs.get("BRIDGE_CONDITION")),
        "status_code": _clean(attrs.get("OPEN_CLOSED_POSTED_041")),
        "scour": _clean(attrs.get("SCOUR_CRITICAL_113")),
        "fracture": _clean(attrs.get("FRACTURE_092A")),
        "year_built": year_built,
        "year_reconstructed": year_rebuilt_i,
        "adt": adt,
        "adt_year": attrs.get("YEAR_ADT_030"),
        "inspect_raw": _clean(attrs.get("DATE_OF_INSPECT_090")),
        "inspect_freq_months": freq,
        "functional_class": _clean(attrs.get("FUNCTIONAL_CLASS_026")),
        "material_code": _clean(attrs.get("STRUCTURE_KIND_043A")),
        "design_code": _clean(attrs.get("STRUCTURE_TYPE_043B")),
    }
    derived = derive(raw)
    raw.update(
        {
            "status_label": derived["status_label"],
            "inspect_date": derived["inspect_date"],
            "age_years": derived["age_years"],
            "inspect_overdue": derived["inspect_overdue"],
            "adt_suspect": derived["adt_suspect"],
            "adt_capped": derived["adt_capped"],
            "is_culvert": derived["is_culvert"],
            "unease_score": derived["unease_score"],
            "headline": derived["headline"],
            "why": derived["why"],
            "worst_component": derived["worst_component"],
            "structure_type": derived["structure_type"],
            "fracture_critical": derived["fracture_critical"],
            "scour_critical": derived["scour_critical"],
            "lowest_rating": derived["lowest_rating"],
            "bridge_condition": derived["bridge_condition"],
        }
    )
    if raw.get("adt_year") is not None:
        try:
            raw["adt_year"] = int(raw["adt_year"])
        except (TypeError, ValueError):
            raw["adt_year"] = None
    return raw


def page_is_complete(
    feature_count: int,
    exceeded: bool,
    offset: int,
    expected_count: int | None,
) -> bool:
    """True when pagination has reached the end of this query."""
    if feature_count == 0:
        return expected_count is not None and offset >= expected_count
    reached_count = (
        expected_count is not None and (offset + feature_count) >= expected_count
    )
    short_page = feature_count < PAGE_SIZE and not exceeded
    return bool(reached_count or short_page)


def fetch_count(session: requests.Session, extra_where: str | None) -> int:
    where = extra_where or "1=1"
    params = {"where": where, "returnCountOnly": "true", "f": "json"}
    last_error = None
    for attempt in range(MAX_RETRIES):
        try:
            response = session.get(Config.NTAD_URL, params=params, timeout=60)
            if response.status_code in {429, 500, 502, 503, 504}:
                time.sleep(1.5 * (attempt + 1))
                continue
            response.raise_for_status()
            payload = response.json()
            if payload.get("error"):
                last_error = payload["error"]
                time.sleep(1.5 * (attempt + 1))
                continue
            return int(payload.get("count") or 0)
        except (requests.RequestException, TypeError, ValueError) as exc:
            last_error = exc
            time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"NTAD count failed: {last_error}")


def fetch_page(session: requests.Session, offset: int, extra_where: str | None) -> dict:
    where = extra_where or "1=1"
    params = {
        "where": where,
        "outFields": ",".join(OUT_FIELDS),
        "returnGeometry": "false",
        "resultOffset": offset,
        "resultRecordCount": PAGE_SIZE,
        "orderByFields": "OBJECTID",
        "f": "json",
    }
    last_error = None
    for attempt in range(MAX_RETRIES):
        try:
            response = session.get(Config.NTAD_URL, params=params, timeout=90)
            if response.status_code in {429, 500, 502, 503, 504}:
                time.sleep(1.5 * (attempt + 1))
                continue
            response.raise_for_status()
            payload = response.json()
            if payload.get("error"):
                last_error = payload["error"]
                time.sleep(1.5 * (attempt + 1))
                continue
            return payload
        except requests.RequestException as exc:
            last_error = exc
            time.sleep(1.5 * (attempt + 1))
        except ValueError as exc:
            last_error = exc
            time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"NTAD page at offset {offset} failed: {last_error}")


def fetch_page_resilient(
    session: requests.Session,
    offset: int,
    extra_where: str | None,
    expected_count: int | None,
) -> dict:
    """Retry blank pages. ArcGIS sometimes returns features=[] mid-inventory."""
    last_payload: dict = {}
    for attempt in range(EMPTY_PAGE_RETRIES):
        payload = fetch_page(session, offset, extra_where)
        last_payload = payload
        features = payload.get("features") or []
        if features:
            return payload
        if page_is_complete(0, bool(payload.get("exceededTransferLimit")), offset, expected_count):
            return payload
        wait = 1.5 * (attempt + 1)
        print(
            f"empty page at offset {offset} (attempt {attempt + 1}/{EMPTY_PAGE_RETRIES}); retry in {wait:.1f}s",
            flush=True,
        )
        time.sleep(wait)
    features = last_payload.get("features") or []
    if not features and expected_count is not None and offset < expected_count:
        raise RuntimeError(
            f"NTAD returned an empty page at offset {offset} "
            f"before expected count {expected_count}"
        )
    return last_payload


def run_ingest(
    max_pages: int | None = None,
    state: str | None = None,
    poor_only: bool = False,
) -> IngestRun:
    print("connecting to database…", flush=True)
    init_db()
    print("schema ready", flush=True)
    db = get_session()
    run = IngestRun(status="running", source_date="2025-06-20")
    db.add(run)
    db.commit()
    db.refresh(run)

    clauses = []
    if state:
        clauses.append(f"STATE_CODE_001='{state.zfill(2)}'")
    if poor_only:
        clauses.append("BRIDGE_CONDITION='P'")
    extra_where = " AND ".join(clauses) if clauses else None
    if extra_where:
        queries = [extra_where]
    else:
        listed = ",".join(f"'{code}'" for code in NBI_STATE_CODES)
        queries = [f"STATE_CODE_001='{code}'" for code in NBI_STATE_CODES]
        queries.append(f"STATE_CODE_001 IS NULL OR STATE_CODE_001 NOT IN ({listed})")

    http = requests.Session()
    http.headers["User-Agent"] = "ThisBridgeIsFine/1.0 (civic inventory; local ingest)"
    pages = 0
    upserted = 0
    skipped = 0

    try:
        for query in queries:
            expected = fetch_count(http, query)
            print(f"query {query} expected {expected}", flush=True)
            offset = 0
            while True:
                if max_pages is not None and pages >= max_pages:
                    break
                if expected == 0:
                    break
                print(f"fetching {query} offset {offset}", flush=True)
                payload = fetch_page_resilient(http, offset, query, expected)
                features = payload.get("features") or []
                if not features:
                    break
                rows = []
                for feature in features:
                    mapped = map_feature(feature.get("attributes") or {})
                    if mapped is None:
                        skipped += 1
                        continue
                    rows.append(mapped)
                if rows:
                    db.execute(UPSERT_SQL, rows)
                    db.commit()
                    upserted += len(rows)
                pages += 1
                offset += len(features)
                print(
                    f"page {pages} offset {offset}/{expected} upserted {upserted} skipped {skipped}",
                    flush=True,
                )
                if page_is_complete(
                    len(features),
                    bool(payload.get("exceededTransferLimit")),
                    offset - len(features),
                    expected,
                ):
                    break
                time.sleep(SLEEP_SECONDS)
            if max_pages is not None and pages >= max_pages:
                break

        run.status = "ok"
        run.finished_at = datetime.now(timezone.utc)
        run.rows_upserted = upserted
        run.rows_skipped = skipped
        run.pages = pages
        db.commit()
        db.refresh(run)
        snapshot = {
            "status": run.status,
            "rows_upserted": run.rows_upserted,
            "rows_skipped": run.rows_skipped,
            "pages": run.pages,
        }
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        run = db.get(IngestRun, run.id) or run
        run.status = "error"
        run.error = str(exc)
        run.finished_at = datetime.now(timezone.utc)
        run.rows_upserted = upserted
        run.rows_skipped = skipped
        run.pages = pages
        db.commit()
        snapshot = {
            "status": run.status,
            "rows_upserted": upserted,
            "rows_skipped": skipped,
            "pages": pages,
        }
        db.close()
        raise
    db.close()
    run.status = snapshot["status"]
    run.rows_upserted = snapshot["rows_upserted"]
    run.rows_skipped = snapshot["rows_skipped"]
    run.pages = snapshot["pages"]
    return run


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Ingest the National Bridge Inventory")
    parser.add_argument("--max-pages", type=int, default=None)
    parser.add_argument("--state", type=str, default=None, help="FIPS state code, e.g. 17")
    parser.add_argument("--poor-only", action="store_true")
    args = parser.parse_args(argv)
    run = run_ingest(max_pages=args.max_pages, state=args.state, poor_only=args.poor_only)
    print(
        f"done status={run.status} upserted={run.rows_upserted} "
        f"skipped={run.rows_skipped} pages={run.pages}"
    )
    return 0 if run.status == "ok" else 1


if __name__ == "__main__":
    sys.exit(main())
