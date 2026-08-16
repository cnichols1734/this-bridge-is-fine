from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from backend.config import Config, normalize_database_url


class Base(DeclarativeBase):
    pass


engine = create_engine(
    normalize_database_url(Config.DATABASE_URL),
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=5,
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

# GIST / bbox indexes are not in the SQLAlchemy model. Create them only
# when pg_catalog says they are missing. `CREATE INDEX IF NOT EXISTS`
# still takes a ShareLock on `bridges` even when the index is already
# there, which deadlocks ingest upserts and ingest_runs work.
BRIDGE_INDEXES = (
    (
        "ix_bridges_geog",
        "CREATE INDEX IF NOT EXISTS ix_bridges_geog ON bridges USING GIST (geog)",
    ),
    (
        "ix_bridges_bbox",
        "CREATE INDEX IF NOT EXISTS ix_bridges_bbox ON bridges (lng, lat)",
    ),
)


def get_session():
    return SessionLocal()


def index_ddl_for(existing_names: set[str]) -> list[str]:
    return [ddl for name, ddl in BRIDGE_INDEXES if name not in existing_names]


def _has_extension(connection, name: str) -> bool:
    return (
        connection.execute(
            text("SELECT 1 FROM pg_extension WHERE extname = :name"),
            {"name": name},
        ).scalar()
        is not None
    )


def _has_column(connection, table: str, column: str) -> bool:
    return (
        connection.execute(
            text(
                """
                SELECT 1
                FROM information_schema.columns
                WHERE table_schema = current_schema()
                  AND table_name = :table
                  AND column_name = :column
                """
            ),
            {"table": table, "column": column},
        ).scalar()
        is not None
    )


def _has_relation(connection, name: str) -> bool:
    return (
        connection.execute(
            text("SELECT to_regclass(:reg) IS NOT NULL"),
            {"reg": name},
        ).scalar()
        is True
    )


def ensure_extensions(connection) -> None:
    if _has_extension(connection, "postgis"):
        return
    connection.execute(text("CREATE EXTENSION IF NOT EXISTS postgis"))


def ensure_ingest_columns(connection) -> None:
    """Additive. create_all will not add columns to an existing ingest_runs table."""
    if not _has_column(connection, "ingest_runs", "checkpoint"):
        connection.execute(
            text("ALTER TABLE ingest_runs ADD COLUMN checkpoint TEXT")
        )
    if not _has_column(connection, "ingest_runs", "checkpoint_offset"):
        connection.execute(
            text(
                "ALTER TABLE ingest_runs "
                "ADD COLUMN checkpoint_offset INTEGER DEFAULT 0"
            )
        )


def ensure_indexes(connection) -> None:
    existing = {
        name for name, _ddl in BRIDGE_INDEXES if _has_relation(connection, name)
    }
    for ddl in index_ddl_for(existing):
        connection.execute(text(ddl))


def init_db() -> None:
    with engine.begin() as connection:
        ensure_extensions(connection)
    from backend import models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    # Keep ingest_runs DDL off the same transaction as bridges indexes.
    # A shared transaction is what deadlocked ingest run 7 against
    # CREATE INDEX ix_bridges_geog.
    with engine.begin() as connection:
        ensure_ingest_columns(connection)
    with engine.begin() as connection:
        ensure_indexes(connection)


if __name__ == "__main__":
    init_db()
    print("schema ready", flush=True)
