"""Release 766: optional daily device summaries, scoped to Tracker workspace DB.

No edits to established tables; only additive table registration.
"""
from datetime import date, datetime

from sqlalchemy import Date, DateTime, Float, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base


class DeviceDay766(Base):
    __tablename__ = "device_days766"
    __table_args__ = (
        UniqueConstraint("source", "measured_on", name="uq_device_day766_source_date"),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source: Mapped[str] = mapped_column(String(80), nullable=False)
    measured_on: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    steps: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sleep_hours: Mapped[float | None] = mapped_column(Float, nullable=True)
    resting_bpm: Mapped[float | None] = mapped_column(Float, nullable=True)
    glucose_avg_mgdl: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
