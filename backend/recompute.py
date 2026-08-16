"""Re-derive scores for rows already in the table.

The ingest owns fetching. This owns nothing but arithmetic: when the scoring
curve changes, every stored row needs the new number without waiting on a
624k-row round trip to ArcGIS. Every input it needs is already a column.
"""

from __future__ import annotations

import time

from sqlalchemy import select, text

from backend.db import get_session, init_db
from backend.models import Bridge
from backend.scoring import unease_score

BATCH = 10_000


def _score(row) -> int:
    return unease_score(
        lowest=row.lowest_rating,
        adt_capped=row.adt_capped or 0,
        status=row.status_code,
        scour=row.scour,
        fracture=row.fracture,
        overdue=bool(row.inspect_overdue),
        year_built=row.year_built,
        culvert=bool(row.is_culvert),
    )


def recompute() -> int:
    init_db()
    db = get_session()
    started = time.time()
    scanned = 0
    changed = 0
    last_id = 0
    statement = text("UPDATE bridges SET unease_score = :score WHERE id = :b_id")
    try:
        while True:
            rows = db.execute(
                select(
                    Bridge.id,
                    Bridge.lowest_rating,
                    Bridge.adt_capped,
                    Bridge.status_code,
                    Bridge.scour,
                    Bridge.fracture,
                    Bridge.inspect_overdue,
                    Bridge.year_built,
                    Bridge.is_culvert,
                    Bridge.unease_score,
                )
                .where(Bridge.id > last_id)
                .order_by(Bridge.id)
                .limit(BATCH)
            ).all()
            if not rows:
                break
            payload = [
                {"b_id": row.id, "score": fresh}
                for row in rows
                if (fresh := _score(row)) != row.unease_score
            ]
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
