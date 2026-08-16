"""Re-derive scores for rows already in the table.

The ingest owns fetching. This owns nothing but arithmetic: when the scoring
curve changes, every stored row needs the new number without waiting on a
624k-row round trip to ArcGIS. Every input it needs is already a column.

The unease_score column stores the public Bridge Score: 0–100, higher is better.
Run this after deploying a scoring change.
"""

from __future__ import annotations

import time

from sqlalchemy import select, text

from backend.db import get_session, init_db
from backend.models import Bridge
from backend.scoring import derive, record_from_bridge

BATCH = 10_000


def _payload(row) -> dict:
    derived = derive(record_from_bridge(row))
    return {
        "b_id": row.id,
        "score": derived["score"],
        "inspect_overdue": bool(derived["inspect_overdue"]),
        "headline": derived.get("headline"),
        "why": derived.get("why"),
        "age_years": derived.get("age_years"),
        "scour_critical": bool(derived.get("scour_critical")),
    }


def recompute() -> int:
    init_db()
    db = get_session()
    started = time.time()
    scanned = 0
    changed = 0
    last_id = 0
    statement = text(
        """
        UPDATE bridges SET
            unease_score = :score,
            inspect_overdue = :inspect_overdue,
            headline = :headline,
            why = :why,
            age_years = :age_years,
            scour_critical = :scour_critical
        WHERE id = :b_id
        """
    )
    try:
        while True:
            rows = db.execute(
                select(
                    Bridge.id,
                    Bridge.deck,
                    Bridge.superstructure,
                    Bridge.substructure,
                    Bridge.culvert,
                    Bridge.lowest_rating,
                    Bridge.bridge_condition,
                    Bridge.status_code,
                    Bridge.scour,
                    Bridge.fracture,
                    Bridge.year_built,
                    Bridge.year_reconstructed,
                    Bridge.adt,
                    Bridge.inspect_raw,
                    Bridge.inspect_date,
                    Bridge.inspect_freq_months,
                    Bridge.functional_class,
                    Bridge.facility_carried,
                    Bridge.material_code,
                    Bridge.design_code,
                    Bridge.unease_score,
                    Bridge.inspect_overdue,
                    Bridge.headline,
                    Bridge.why,
                    Bridge.age_years,
                    Bridge.scour_critical,
                )
                .where(Bridge.id > last_id)
                .order_by(Bridge.id)
                .limit(BATCH)
            ).all()
            if not rows:
                break
            payload = []
            for row in rows:
                fresh = _payload(row)
                if (
                    fresh["score"] != row.unease_score
                    or fresh["inspect_overdue"] != bool(row.inspect_overdue)
                    or fresh["headline"] != row.headline
                    or fresh["why"] != row.why
                    or fresh["age_years"] != row.age_years
                    or fresh["scour_critical"] != bool(row.scour_critical)
                ):
                    payload.append(fresh)
            if payload:
                db.execute(statement, payload)
                db.commit()
                db.expire_all()
                changed += len(payload)
            scanned += len(rows)
            last_id = rows[-1].id
            print(
                f"recompute: {scanned:,} scanned, {changed:,} rewritten "
                f"({time.time() - started:.0f}s)",
                flush=True,
            )
    finally:
        db.close()
    print(
        f"recompute: done. {scanned:,} scanned, {changed:,} rewritten "
        f"in {time.time() - started:.0f}s",
        flush=True,
    )
    return changed


if __name__ == "__main__":
    recompute()
