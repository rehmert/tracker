"""Release 654 additive workout tables; data stays in Tracker's scoped user DB."""
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base

KINDS654 = ("selectorized", "plate_loaded", "free_weight", "bodyweight")


class WorkoutEquipment654(Base):
    __tablename__ = "workout_equipment654"
    __table_args__ = (CheckConstraint(
        "kind IN ('selectorized','plate_loaded','free_weight','bodyweight')",
        name="ck_workout654_kind",
    ),)
    id: Mapped[int] = mapped_column(primary_key=True)
    gym: Mapped[str] = mapped_column(String(140), default="Merritt Athletic Club - Eldersburg")
    name: Mapped[str] = mapped_column(String(140), nullable=False)
    kind: Mapped[str] = mapped_column(String(24), nullable=False)
    manufacturer: Mapped[str] = mapped_column(String(100), default="")
    model: Mapped[str] = mapped_column(String(140), default="")
    qr_value: Mapped[str | None] = mapped_column(String(1024), nullable=True, unique=True)
    seat_setting: Mapped[str] = mapped_column(String(80), default="")
    setup_notes: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class WorkoutSession654(Base):
    __tablename__ = "workout_sessions654"
    id: Mapped[int] = mapped_column(primary_key=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class WorkoutSet654(Base):
    __tablename__ = "workout_sets654"
    __table_args__ = (
        CheckConstraint("weight_lb >= 0 AND weight_lb <= 2000", name="ck_workout654_weight"),
        CheckConstraint("reps >= 1 AND reps <= 200", name="ck_workout654_reps"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("workout_sessions654.id", ondelete="CASCADE"), index=True)
    equipment_id: Mapped[int] = mapped_column(ForeignKey("workout_equipment654.id", ondelete="RESTRICT"), index=True)
    weight_lb: Mapped[float] = mapped_column(Float, nullable=False)
    reps: Mapped[int] = mapped_column(Integer, nullable=False)
    effort: Mapped[int | None] = mapped_column(Integer, nullable=True)
    performed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
