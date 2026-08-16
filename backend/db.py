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


def get_session():
    return SessionLocal()


def ensure_extensions(connection) -> None:
    connection.execute(text("CREATE EXTENSION IF NOT EXISTS postgis"))


def ensure_ingest_columns(connection) -> None:
    """Additive. create_all will not add columns to an existing ingest_runs table."""
    connection.execute(
        text("ALTER TABLE ingest_runs ADD COLUMN IF NOT EXISTS checkpoint TEXT")
    )
    connection.execute(
        text(
            "ALTER TABLE ingest_runs "
            "ADD COLUMN IF NOT EXISTS checkpoint_offset INTEGER DEFAULT 0"
        )
    )


def init_db() -> None:
    with engine.begin() as connection:
        ensure_extensions(connection)
    from backend import models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    with engine.begin() as connection:
        ensure_ingest_columns(connection)
        connection.execute(
            text(
                "CREATE INDEX IF NOT EXISTS ix_bridges_geog "
                "ON bridges USING GIST (geog)"
            )
        )
        connection.execute(
            text(
                "CREATE INDEX IF NOT EXISTS ix_bridges_bbox "
                "ON bridges (lng, lat)"
            )
        )
