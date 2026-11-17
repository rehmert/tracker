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
