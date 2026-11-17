"""Release 668 additive workout planning, audit, semantics and offline tables.

All tables are scoped to the existing authenticated user's SQLite database.
No 654/655/667 table or previously logged workout is migrated or rewritten.
"""
from datetime import datetime
from sqlalchemy import (
    CheckConstraint, DateTime, Float, ForeignKey, Integer, String, Text,
    UniqueConstraint, func,
)
from sqlalchemy.orm import Mapped, mapped_column
from .db import Base


class WorkoutTrainingDay668(Base):
    __tablename__ = "workout_training_days668"
    __table_args__ = (
        CheckConstraint("weekday BETWEEN 0 AND 6", name="ck_workout668_weekday"),
        UniqueConstraint("weekday", "routine_id", name="uq_workout668_day_routine"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    weekday: Mapped[int] = mapped_column(Integer, nullable=False)
    routine_id: Mapped[int] = mapped_column(
        ForeignKey("workout_routines655.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    note: Mapped[str] = mapped_column(String(120), default="", nullable=False)


class WorkoutRoutineGroup668(Base):
    __tablename__ = "workout_routine_groups668"
    __table_args__ = (
        CheckConstraint("mode IN ('superset','circuit')", name="ck_workout668_group_mode"),
    )
    routine_item_id: Mapped[int] = mapped_column(
        ForeignKey("workout_routine_items655.id", ondelete="CASCADE"), primary_key=True,
    )
    label: Mapped[str] = mapped_column(String(20), nullable=False)
    mode: Mapped[str] = mapped_column(String(12), nullable=False)


class WorkoutSessionSubstitution668(Base):
    __tablename__ = "workout_session_substitutions668"
    __table_args__ = (
        UniqueConstraint("session_id", "alternate_equipment_id", name="uq_workout668_alternate"),
        CheckConstraint("original_equipment_id != alternate_equipment_id", name="ck_workout668_sub_distinct"),
    )
    session_id: Mapped[int] = mapped_column(
        ForeignKey("workout_sessions654.id", ondelete="CASCADE"), primary_key=True,
    )
    original_equipment_id: Mapped[int] = mapped_column(
        ForeignKey("workout_equipment654.id", ondelete="RESTRICT"), primary_key=True,
    )
    alternate_equipment_id: Mapped[int] = mapped_column(
        ForeignKey("workout_equipment654.id", ondelete="RESTRICT"), nullable=False,
    )
    assigned_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)


class WorkoutSetAudit668(Base):
    __tablename__ = "workout_set_audit668"
    __table_args__ = (
        CheckConstraint("action IN ('edit','delete')", name="ck_workout668_audit_action"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(
        ForeignKey("workout_sessions654.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    # Intentionally plain ID, not FK: deletion must never erase its audit trail.
    original_set_id: Mapped[int] = mapped_column(Integer, nullable=False)
    action: Mapped[str] = mapped_column(String(10), nullable=False)
    before_json: Mapped[str] = mapped_column(Text, nullable=False)
    after_json: Mapped[str] = mapped_column(Text, nullable=False)
    reason: Mapped[str] = mapped_column(String(300), nullable=False)
    changed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)


class WorkoutLoadSemantics668(Base):
    __tablename__ = "workout_load_semantics668"
    __table_args__ = (
        CheckConstraint("mode IN ('as_recorded','per_hand','added_bodyweight')", name="ck_workout668_load_mode"),
    )
    equipment_id: Mapped[int] = mapped_column(
        ForeignKey("workout_equipment654.id", ondelete="CASCADE"), primary_key=True,
    )
    mode: Mapped[str] = mapped_column(String(24), nullable=False)


class WorkoutImportReceipt668(Base):
    __tablename__ = "workout_import_receipts668"
    digest: Mapped[str] = mapped_column(String(64), primary_key=True)
    sessions_created: Mapped[int] = mapped_column(Integer, nullable=False)
    imported_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)


class WorkoutOfflineReceipt668(Base):
    __tablename__ = "workout_offline_receipts668"
    token: Mapped[str] = mapped_column(String(36), primary_key=True)
    session_id: Mapped[int] = mapped_column(
        ForeignKey("workout_sessions654.id", ondelete="CASCADE"), index=True, nullable=False,
    )
    # Keep the original ID as an immutable idempotency tombstone even
    # if the user later deletes or corrects the actual recorded set.
    set_id: Mapped[int] = mapped_column(Integer, nullable=False)
    received_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)
