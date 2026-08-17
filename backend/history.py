"""Annual NBI condition snapshots. Current ingest plus FHWA ASCII backfill."""

from __future__ import annotations

import argparse
import csv
import io
import re
import sys
import zipfile
from pathlib import Path

import requests
from sqlalchemy import text

from backend.db import get_session, init_db
from backend.lookups import parse_optional_int, rating_int

YEAR_RE = re.compile(r"(19|20)\d{2}")
STATE_RE = re.compile(r"^\d{2}$")
ZIP_HREF_RE = re.compile(
    r'href=["\']([^"\']+\.zip)["\'][^>]*>(.*?)</a>',
    re.IGNORECASE | re.DOTALL,
)
HEADING_RE = re.compile(r"<h[1-6][^>]*>(.*?)</h[1-6]>", re.IGNORECASE | re.DOTALL)
TAG_RE = re.compile(r"<[^>]+>")
ASCII_PAGE = "https://www.fhwa.dot.gov/bridge/nbi/ascii{year}.cfm"
DEFAULT_YEARS = ("2021", "2022", "2023", "2024", "2025")

HISTORY_UPSERT_SQL = text(
    """
    INSERT INTO bridge_history (
        state_code, structure_number, nbi_year,
        lowest_rating, deck, superstructure, substructure, culvert
    ) VALUES (
        :state_code, :structure_number, :nbi_year,
        :lowest_rating, :deck, :superstructure, :substructure, :culvert
    )
    ON CONFLICT (state_code, structure_number, nbi_year) DO UPDATE SET
        lowest_rating = EXCLUDED.lowest_rating,
        deck = EXCLUDED.deck,
        superstructure = EXCLUDED.superstructure,
        substructure = EXCLUDED.substructure,
        culvert = EXCLUDED.culvert
    """
)


def nbi_year_from_value(value) -> str | None:
    if value is None:
        return None
    match = YEAR_RE.search(str(value).strip())
    return match.group(0) if match else None


def _clean(value) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        text_value = value.strip().strip("'")
        return text_value or None
    return str(value).strip() or None


def _field(row: dict, *names: str):
    upper = {str(key).strip().upper(): value for key, value in row.items()}
    for name in names:
        if name in upper:
            return upper[name]
    return None


def history_row(
    *,
    state_code: str | None,
    structure_number: str | None,
    nbi_year: str | None,
    deck=None,
    superstructure=None,
    substructure=None,
    culvert=None,
    lowest_rating=None,
) -> dict | None:
    state = _clean(state_code)
    structure = _clean(structure_number)
    year = nbi_year_from_value(nbi_year)
    if not state or not structure or not year:
        return None
    if state.isdigit():
        state = state.zfill(2)[-2:]
    if not STATE_RE.fullmatch(state):
        return None
    deck_c = _clean(deck)
    super_c = _clean(superstructure)
    sub_c = _clean(substructure)
    culvert_c = _clean(culvert)
    lowest = parse_optional_int(lowest_rating)
    if lowest is None:
        ratings = [
            rating_int(deck_c),
            rating_int(super_c),
            rating_int(sub_c),
            rating_int(culvert_c),
        ]
        present = [n for n in ratings if n is not None]
        lowest = min(present) if present else None
    return {
        "state_code": state,
        "structure_number": structure,
        "nbi_year": year,
        "lowest_rating": lowest,
        "deck": deck_c,
        "superstructure": super_c,
        "substructure": sub_c,
        "culvert": culvert_c,
    }


def history_row_from_mapped(mapped: dict) -> dict | None:
    return history_row(
        state_code=mapped.get("state_code"),
        structure_number=mapped.get("structure_number"),
        nbi_year=mapped.get("nbi_year"),
        deck=mapped.get("deck"),
        superstructure=mapped.get("superstructure"),
        substructure=mapped.get("substructure"),
        culvert=mapped.get("culvert"),
        lowest_rating=mapped.get("lowest_rating"),
    )


def parse_history_record(attrs: dict, year_hint: str | None = None) -> dict | None:
    return history_row(
        state_code=_field(attrs, "STATE_CODE_001", "STATE_CODE"),
        structure_number=_field(attrs, "STRUCTURE_NUMBER_008", "STRUCTURE_NUMBER"),
        nbi_year=_field(attrs, "YEAR", "DATE") or year_hint,
        deck=_field(attrs, "DECK_COND_058", "DECK"),
        superstructure=_field(attrs, "SUPERSTRUCTURE_COND_059", "SUPERSTRUCTURE"),
        substructure=_field(attrs, "SUBSTRUCTURE_COND_060", "SUBSTRUCTURE"),
        culvert=_field(attrs, "CULVERT_COND_062", "CULVERT"),
        lowest_rating=_field(attrs, "LOWEST_RATING"),
    )


def _plain(html_bit: str) -> str:
    return TAG_RE.sub(" ", html_bit or "").lower()


def _heading_before(html: str, pos: int) -> str:
    heads = [m for m in HEADING_RE.finditer(html) if m.end() <= pos]
    if not heads:
        return ""
    return _plain(heads[-1].group(1))


def pick_delimited_zip(html: str, page_url: str) -> str | None:
    matches = list(ZIP_HREF_RE.finditer(html))
    if not matches:
        return None
    scored = []
    for match in matches:
        href = match.group(1)
        label = _plain(match.group(2))
        heading = _heading_before(html, match.start())
        context = f"{heading} {label}"
        name = href.lower()
        score = 0
        if "delimit" in name or "comma" in name or name.endswith("del.zip"):
            score += 5
        if "delimit" in context or "comma" in context:
            score += 4
        if "single file" in context or "in a single file" in context:
            score += 2
        if "all" in name or "nation" in name:
            score += 1
        if "element" in name or "element" in context:
            score -= 6
        if "no delimiter" in context:
            score -= 4
        scored.append((score, href))
    scored.sort(key=lambda item: item[0], reverse=True)
    best = scored[0][1]
    if best.startswith("http"):
        return best
    if best.startswith("/"):
        return f"https://www.fhwa.dot.gov{best}"
    base = page_url.rsplit("/", 1)[0]
    return f"{base}/{best}"


def _csv_reader(text_blob: str):
    sample = text_blob[:4096]
    dialect = csv.excel
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",\t|")
    except csv.Error:
        pass
    return csv.DictReader(io.StringIO(text_blob), dialect=dialect, quotechar="'")


def parse_history_text(text_blob: str, year_hint: str | None = None) -> list[dict]:
    rows = []
    for raw in _csv_reader(text_blob):
        if not raw:
            continue
        mapped = parse_history_record(raw, year_hint)
        if mapped:
            rows.append(mapped)
    return rows


def extract_zip_text(payload: bytes) -> str:
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        names = [
            name
            for name in archive.namelist()
            if not name.endswith("/") and not name.startswith("__")
        ]
        if not names:
            raise RuntimeError("zip had no files")
        preferred = next(
            (
                name
                for name in names
                if name.lower().endswith((".txt", ".csv", ".asc"))
            ),
            names[0],
        )
        return archive.read(preferred).decode("latin-1", errors="replace")


def fetch_year_zip(session: requests.Session, year: str) -> bytes:
    page_url = ASCII_PAGE.format(year=year)
    page = session.get(page_url, timeout=60)
    page.raise_for_status()
    zip_url = pick_delimited_zip(page.text, page_url)
    if not zip_url:
        raise RuntimeError(f"no delimited zip link on {page_url}")
    print(f"downloading {year} from {zip_url}", flush=True)
    response = session.get(zip_url, timeout=180)
    response.raise_for_status()
    return response.content


def upsert_history(db, rows: list[dict], batch: int = 2000) -> int:
    if not rows:
        return 0
    written = 0
    for start in range(0, len(rows), batch):
        chunk = rows[start : start + batch]
        db.execute(HISTORY_UPSERT_SQL, chunk)
        written += len(chunk)
    db.commit()
    return written


def load_history_years(years: list[str], cache_dir: Path | None = None) -> dict[str, int]:
    init_db()
    db = get_session()
    http = requests.Session()
    http.headers["User-Agent"] = "ThisBridgeIsFine/1.0 (civic inventory; NBI history)"
    counts: dict[str, int] = {}
    try:
        for year in years:
            raw = None
            if cache_dir:
                cached = cache_dir / f"nbi{year}.zip"
                if cached.exists():
                    raw = cached.read_bytes()
            if raw is None:
                raw = fetch_year_zip(http, year)
                if cache_dir:
                    cache_dir.mkdir(parents=True, exist_ok=True)
                    (cache_dir / f"nbi{year}.zip").write_bytes(raw)
            text_blob = extract_zip_text(raw)
            rows = parse_history_text(text_blob, year)
            counts[year] = upsert_history(db, rows)
            print(f"year {year} upserted {counts[year]}", flush=True)
    finally:
        db.close()
    return counts


def condition_trend(rows: list[dict]) -> dict | None:
    points = []
    for row in rows:
        year = nbi_year_from_value(row.get("nbi_year"))
        rating = parse_optional_int(row.get("lowest_rating"))
        if year is None or rating is None:
            continue
        points.append({"year": int(year), "rating": rating})
    points.sort(key=lambda item: item["year"])
    unique: dict[int, int] = {}
    for point in points:
        unique[point["year"]] = point["rating"]
    series = [{"year": year, "rating": unique[year]} for year in sorted(unique)]
    if len(series) < 2:
        return None
    ratings = [item["rating"] for item in series]
    first_year = series[0]["year"]
    delta = ratings[-1] - ratings[0]
    spread = max(ratings) - min(ratings)
    if spread <= 1:
        insight = f"Condition has remained relatively stable since {first_year}."
    elif delta <= -2:
        insight = f"Condition has declined since {first_year}."
    elif delta >= 2:
        insight = f"Condition has improved since {first_year}."
    else:
        insight = f"Condition has changed since {first_year}."
    return {"points": series[-5:], "insight": insight}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Load NBI condition history")
    parser.add_argument(
        "--years",
        default=",".join(DEFAULT_YEARS),
        help="Comma-separated NBI years, e.g. 2021,2022,2023,2024,2025",
    )
    parser.add_argument("--cache-dir", default=None)
    args = parser.parse_args(argv)
    years = [part.strip() for part in args.years.split(",") if part.strip()]
    cache = Path(args.cache_dir) if args.cache_dir else None
    counts = load_history_years(years, cache)
    total = sum(counts.values())
    print(f"done years={len(counts)} rows={total}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
