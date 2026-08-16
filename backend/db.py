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


def init_db() -> None:
    with engine.begin() as connection:
        ensure_extensions(connection)
    from backend import models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    with engine.begin() as connection:
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
