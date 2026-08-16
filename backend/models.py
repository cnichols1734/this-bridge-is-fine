from datetime import date, datetime

from geoalchemy2 import Geography
from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Float,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from backend.db import Base


class Bridge(Base):
    __tablename__ = "bridges"
    __table_args__ = (
        UniqueConstraint("state_code", "structure_number", name="uq_bridge_identity"),
        Index("ix_bridges_unease", "unease_score"),
        Index("ix_bridges_condition", "bridge_condition"),
        Index("ix_bridges_lowest", "lowest_rating"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    state_code: Mapped[str] = mapped_column(String(2), nullable=False)
    structure_number: Mapped[str] = mapped_column(String(32), nullable=False)
    nbi_year: Mapped[str | None] = mapped_column(String(4))

    lat: Mapped[float] = mapped_column(Float, nullable=False)
    lng: Mapped[float] = mapped_column(Float, nullable=False)
    geog = mapped_column(Geography(geometry_type="POINT", srid=4326), nullable=False)

    facility_carried: Mapped[str | None] = mapped_column(String(64))
    feature_crossed: Mapped[str | None] = mapped_column(String(64))
    location_text: Mapped[str | None] = mapped_column(String(64))

    deck: Mapped[str | None] = mapped_column(String(2))
    superstructure: Mapped[str | None] = mapped_column(String(2))
    substructure: Mapped[str | None] = mapped_column(String(2))
    culvert: Mapped[str | None] = mapped_column(String(2))
    lowest_rating: Mapped[int | None] = mapped_column(Integer)
    bridge_condition: Mapped[str | None] = mapped_column(String(1))

    status_code: Mapped[str | None] = mapped_column(String(2))
    status_label: Mapped[str | None] = mapped_column(String(48))
    scour: Mapped[str | None] = mapped_column(String(2))
    fracture: Mapped[str | None] = mapped_column(String(8))
    year_built: Mapped[int | None] = mapped_column(Integer)
    year_reconstructed: Mapped[int | None] = mapped_column(Integer)
    adt: Mapped[int | None] = mapped_column(Integer)
    adt_year: Mapped[int | None] = mapped_column(Integer)
    inspect_raw: Mapped[str | None] = mapped_column(String(8))
    inspect_date: Mapped[date | None] = mapped_column(Date)
    inspect_freq_months: Mapped[int | None] = mapped_column(Integer)
    functional_class: Mapped[str | None] = mapped_column(String(4))
    material_code: Mapped[str | None] = mapped_column(String(2))
    design_code: Mapped[str | None] = mapped_column(String(4))
    structure_type: Mapped[str | None] = mapped_column(String(80))

    age_years: Mapped[int | None] = mapped_column(Integer)
    inspect_overdue: Mapped[bool] = mapped_column(Boolean, default=False)
    adt_suspect: Mapped[bool] = mapped_column(Boolean, default=False)
    adt_capped: Mapped[int] = mapped_column(Integer, default=0)
    is_culvert: Mapped[bool] = mapped_column(Boolean, default=False)
    unease_score: Mapped[int] = mapped_column(Integer, default=0)
    headline: Mapped[str | None] = mapped_column(Text)
    why: Mapped[str | None] = mapped_column(Text)
    worst_component: Mapped[str | None] = mapped_column(String(24))
    fracture_critical: Mapped[bool] = mapped_column(Boolean, default=False)
    scour_critical: Mapped[bool] = mapped_column(Boolean, default=False)

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class IngestRun(Base):
    __tablename__ = "ingest_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(16), default="running")
    rows_upserted: Mapped[int] = mapped_column(Integer, default=0)
    rows_skipped: Mapped[int] = mapped_column(Integer, default=0)
    pages: Mapped[int] = mapped_column(Integer, default=0)
    source_date: Mapped[str | None] = mapped_column(String(16))
    error: Mapped[str | None] = mapped_column(Text)
    checkpoint: Mapped[str | None] = mapped_column(Text)
