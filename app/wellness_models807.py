"""Additive health records for the authenticated Tracker workspace database."""
from datetime import date, datetime
from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from .db import Base

class WellnessPreferences807(Base):
    __tablename__ = "wellness_preferences807"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    metrics_json: Mapped[str] = mapped_column(Text, default="[]", nullable=False)

class WellnessDay807(Base):
    __tablename__ = "wellness_days807"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    day: Mapped[date] = mapped_column(Date, unique=True, nullable=False, index=True)
    values_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    notes: Mapped[str] = mapped_column(Text, nullable=False, default="")

class Symptom807(Base):
    __tablename__ = "wellness_symptoms807"
    __table_args__ = (
        CheckConstraint("severity BETWEEN 1 AND 5", name="ck_symptom807_severity"),
        CheckConstraint("resolved_at IS NULL OR resolved_at >= onset_at", name="ck_symptom807_dates"),
        Index("ix_symptom807_onset", "onset_at"),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    symptom: Mapped[str] = mapped_column(String(80), nullable=False)
    severity: Mapped[int] = mapped_column(Integer, nullable=False)
    onset_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    notes: Mapped[str] = mapped_column(Text, nullable=False, default="")

class SiteReaction807(Base):
    __tablename__ = "site_reactions807"
    __table_args__ = (
        CheckConstraint("(dose_id IS NOT NULL AND blend_dose_id IS NULL) OR (dose_id IS NULL AND blend_dose_id IS NOT NULL)", name="ck_reaction807_parent"),
        CheckConstraint("severity BETWEEN 0 AND 5", name="ck_reaction807_severity"),
        CheckConstraint("resolved_at IS NULL OR resolved_at >= onset_at", name="ck_reaction807_dates"),
        Index("ix_reaction807_dose", "dose_id"),
        Index("ix_reaction807_blend", "blend_dose_id"),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    dose_id: Mapped[int | None] = mapped_column(ForeignKey("dose_logs.id", ondelete="CASCADE"), nullable=True)
    blend_dose_id: Mapped[int | None] = mapped_column(ForeignKey("blend_doses.id", ondelete="CASCADE"), nullable=True)
    site: Mapped[str] = mapped_column(String(80), nullable=False)
    reaction: Mapped[str] = mapped_column(String(80), nullable=False)
    severity: Mapped[int] = mapped_column(Integer, nullable=False)
    onset_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    notes: Mapped[str] = mapped_column(Text, nullable=False, default="")
