"""Release 668 additive workout schedule and training-group metadata.

Scoped per-account SQLite DB; never changes historical 654/655/667 tables.
Migration review and verified backups are mandatory before deployment.
"""
from datetime import date, datetime

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base


class WorkoutRoutineSchedule668(Base):
    __tablename__ = "workout_routine_schedule668"
    __table_args__ = (
        CheckConstraint("length(weekdays) <= 13", name="ck_workout668_schedule_days_len"),
    )
    routine_id: Mapped[int] = mapped_column(
        ForeignKey("workout_routines655.id", ondelete="CASCADE"), primary_key=True
    )
    weekdays: Mapped[str] = mapped_column(String(13), nullable=False)
    start_on: Mapped[date] = mapped_column(Date, nullable=False)
    end_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)


class WorkoutRoutineGroup668(Base):
    __tablename__ = "workout_routine_groups668"
    __table_args__ = (
        UniqueConstraint("routine_id", "group_name", name="uq_workout668_routine_group_name"),
        CheckConstraint("group_type IN ('superset','circuit')", name="ck_workout668_group_type"),
        CheckConstraint("rounds BETWEEN 1 AND 20", name="ck_workout668_group_rounds"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    routine_id: Mapped[int] = mapped_column(
        ForeignKey("workout_routines655.id", ondelete="CASCADE"), nullable=False, index=True
    )
    group_name: Mapped[str] = mapped_column(String(100), nullable=False)
    group_type: Mapped[str] = mapped_column(String(16), nullable=False)
    rounds: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)


class WorkoutRoutineGroupMember668(Base):
    __tablename__ = "workout_routine_group_members668"
    __table_args__ = (
        UniqueConstraint("routine_item_id", name="uq_workout668_group_single_membership"),
        CheckConstraint("position >= 0", name="ck_workout668_group_position"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    group_id: Mapped[int] = mapped_column(
        ForeignKey("workout_routine_groups668.id", ondelete="CASCADE"), nullable=False, index=True
    )
    routine_item_id: Mapped[int] = mapped_column(
        ForeignKey("workout_routine_items655.id", ondelete="CASCADE"), nullable=False
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)


class WorkoutSetCorrection668(Base):
    __tablename__ = "workout_set_corrections668"
    __table_args__ = (
        CheckConstraint("length(reason) BETWEEN 3 AND 500", name="ck_workout668_correction_reason"),
        CheckConstraint("old_weight_lb BETWEEN 0 AND 2000", name="ck_workout668_correction_old_weight"),
        CheckConstraint("new_weight_lb BETWEEN 0 AND 2000", name="ck_workout668_correction_new_weight"),
        CheckConstraint("old_reps BETWEEN 1 AND 200", name="ck_workout668_correction_old_reps"),
        CheckConstraint("new_reps BETWEEN 1 AND 200", name="ck_workout668_correction_new_reps"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    set_id: Mapped[int] = mapped_column(
        ForeignKey("workout_sets654.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    old_weight_lb: Mapped[float] = mapped_column(nullable=False)
    new_weight_lb: Mapped[float] = mapped_column(nullable=False)
    old_reps: Mapped[int] = mapped_column(Integer, nullable=False)
    new_reps: Mapped[int] = mapped_column(Integer, nullable=False)
    old_effort: Mapped[int | None] = mapped_column(Integer, nullable=True)
    new_effort: Mapped[int | None] = mapped_column(Integer, nullable=True)
    old_type: Mapped[str] = mapped_column(String(16), nullable=False)
    new_type: Mapped[str] = mapped_column(String(16), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    corrected_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)


class WorkoutOfflineReceipt668(Base):
    """An offline client action becomes one actual set, at most once."""
    __tablename__ = "workout_offline_receipts668"
    __table_args__ = (
        UniqueConstraint("client_key", name="uq_workout668_offline_key"),
        CheckConstraint("length(client_key) = 36", name="ck_workout668_offline_key"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    client_key: Mapped[str] = mapped_column(String(36), nullable=False)
    session_id: Mapped[int] = mapped_column(
        ForeignKey("workout_sessions654.id", ondelete="RESTRICT"), nullable=False
    )
    set_id: Mapped[int] = mapped_column(
        ForeignKey("workout_sets654.id", ondelete="RESTRICT"), nullable=False
    )
    synced_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)


class WorkoutEquipmentLoad668(Base):
    """Interpretation metadata; never rescales stored historical set loads."""
    __tablename__ = "workout_equipment_load668"
    __table_args__ = (
        CheckConstraint(
            "load_mode IN ('stack','total_plates','per_side','pair_total','bodyweight_added')",
            name="ck_workout668_load_mode",
        ),
        CheckConstraint("multiplier > 0 AND multiplier <= 10", name="ck_workout668_load_multiplier"),
        CheckConstraint("offset_lb >= 0 AND offset_lb <= 500", name="ck_workout668_load_offset"),
    )
    equipment_id: Mapped[int] = mapped_column(
        ForeignKey("workout_equipment654.id", ondelete="CASCADE"), primary_key=True
    )
    load_mode: Mapped[str] = mapped_column(String(24), nullable=False, default="stack")
    multiplier: Mapped[float] = mapped_column(nullable=False, default=1.0)
    offset_lb: Mapped[float] = mapped_column(nullable=False, default=0.0)
    note: Mapped[str] = mapped_column(Text, nullable=False, default="")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)
