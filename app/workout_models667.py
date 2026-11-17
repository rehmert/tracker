"""Release 667 additive, scoped workout planning and execution models.

Existing Workout654/655 tables and data are unchanged. Plans are mutable per
routine item; session targets are frozen at routine start; set kinds are
optional annotations attached to actual recorded sets.
"""
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base


class WorkoutRoutineConfig667(Base):
    __tablename__ = "workout_routine_config667"
    __table_args__ = (
        CheckConstraint("rest_seconds IN (30,45,60,75,90,120,150,180,240,300,360,420,480,600)", name="ck_workout667_routine_rest"),
    )
    routine_id: Mapped[int] = mapped_column(
        ForeignKey("workout_routines655.id", ondelete="CASCADE"), primary_key=True,
    )
    rest_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=90)


class WorkoutRoutineTarget667(Base):
    __tablename__ = "workout_routine_targets667"
    __table_args__ = (
        CheckConstraint("target_sets IS NULL OR target_sets BETWEEN 1 AND 20", name="ck_workout667_target_sets"),
        CheckConstraint("target_reps IS NULL OR target_reps BETWEEN 1 AND 200", name="ck_workout667_target_reps"),
        CheckConstraint("target_weight_lb IS NULL OR (target_weight_lb >= 0 AND target_weight_lb <= 2000)", name="ck_workout667_target_weight"),
        CheckConstraint("(target_sets IS NULL AND target_reps IS NULL AND target_weight_lb IS NULL) OR (target_sets IS NOT NULL AND target_reps IS NOT NULL AND target_weight_lb IS NOT NULL)", name="ck_workout667_target_complete"),
        CheckConstraint("rest_seconds IS NULL OR rest_seconds IN (30,45,60,75,90,120,150,180,240,300,360,420,480,600)", name="ck_workout667_target_rest"),
    )
    routine_item_id: Mapped[int] = mapped_column(
        ForeignKey("workout_routine_items655.id", ondelete="CASCADE"),
        primary_key=True,
    )
    target_sets: Mapped[int | None] = mapped_column(Integer, nullable=True)
    target_reps: Mapped[int | None] = mapped_column(Integer, nullable=True)
    target_weight_lb: Mapped[float | None] = mapped_column(Float, nullable=True)
    setup_note: Mapped[str] = mapped_column(Text, nullable=False, default="")
    rest_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.now)


class WorkoutSessionTarget667(Base):
    __tablename__ = "workout_session_targets667"
    __table_args__ = (
        CheckConstraint("target_sets BETWEEN 1 AND 20", name="ck_workout667_session_sets"),
        CheckConstraint("target_reps BETWEEN 1 AND 200", name="ck_workout667_session_reps"),
        CheckConstraint("target_weight_lb >= 0 AND target_weight_lb <= 2000", name="ck_workout667_session_weight"),
        CheckConstraint("rest_seconds IN (30,45,60,75,90,120,150,180,240,300,360,420,480,600)", name="ck_workout667_session_rest"),
    )
    session_id: Mapped[int] = mapped_column(
        ForeignKey("workout_sessions654.id", ondelete="CASCADE"), primary_key=True,
    )
    equipment_id: Mapped[int] = mapped_column(
        ForeignKey("workout_equipment654.id", ondelete="RESTRICT"), primary_key=True,
    )
    target_sets: Mapped[int] = mapped_column(Integer, nullable=False)
    target_reps: Mapped[int] = mapped_column(Integer, nullable=False)
    target_weight_lb: Mapped[float] = mapped_column(Float, nullable=False)
    rest_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    setup_note: Mapped[str] = mapped_column(Text, nullable=False, default="")
    captured_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.now)


class WorkoutSetType667(Base):
    __tablename__ = "workout_set_types667"
    __table_args__ = (
        CheckConstraint("set_type IN ('working','warmup')", name="ck_workout667_set_type"),
    )
    set_id: Mapped[int] = mapped_column(
        ForeignKey("workout_sets654.id", ondelete="CASCADE"), primary_key=True,
    )
    set_type: Mapped[str] = mapped_column(String(16), nullable=False)
