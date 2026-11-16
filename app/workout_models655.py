"""Release 655 additive workout routines and session association.

No alteration of existing Release 654 workout tables or historic set records.
Stored in the authenticated user's existing scoped SQLite database.
"""
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base


class WorkoutRoutine655(Base):
    __tablename__ = "workout_routines655"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)


class WorkoutRoutineItem655(Base):
    __tablename__ = "workout_routine_items655"
    __table_args__ = (
        UniqueConstraint("routine_id", "equipment_id", name="uq_workout655_routine_equipment"),
        CheckConstraint("position >= 0", name="ck_workout655_position_nonnegative"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    routine_id: Mapped[int] = mapped_column(
        ForeignKey("workout_routines655.id", ondelete="CASCADE"), index=True, nullable=False
    )
    equipment_id: Mapped[int] = mapped_column(
        ForeignKey("workout_equipment654.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)


class WorkoutSessionRoutine655(Base):
    __tablename__ = "workout_session_routines655"
    session_id: Mapped[int] = mapped_column(
        ForeignKey("workout_sessions654.id", ondelete="CASCADE"), primary_key=True
    )
    routine_id: Mapped[int] = mapped_column(
        ForeignKey("workout_routines655.id", ondelete="RESTRICT"), index=True, nullable=False
    )
