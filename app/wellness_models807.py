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

class AdministrationContext807(Base):
    __tablename__ = "administration_context807"
    __table_args__ = (
        CheckConstraint("(dose_id IS NOT NULL AND blend_dose_id IS NULL AND regimen_entry_id IS NULL) OR (dose_id IS NULL AND blend_dose_id IS NOT NULL AND regimen_entry_id IS NULL) OR (dose_id IS NULL AND blend_dose_id IS NULL AND regimen_entry_id IS NOT NULL)", name="ck_admin_context807_parent"),
        CheckConstraint("route IN ('','subcutaneous','intramuscular','other')", name="ck_admin_context807_route"),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    dose_id: Mapped[int | None] = mapped_column(ForeignKey("dose_logs.id", ondelete="CASCADE"), unique=True)
    blend_dose_id: Mapped[int | None] = mapped_column(ForeignKey("blend_doses.id", ondelete="CASCADE"), unique=True)
    regimen_entry_id: Mapped[int | None] = mapped_column(ForeignKey("regimen_entries635.id", ondelete="CASCADE"), unique=True)
    route: Mapped[str] = mapped_column(String(24), nullable=False, default="")
    # Store the explicit selected calendar protocol, not a guessed match.
    protocol_id: Mapped[int | None] = mapped_column(ForeignKey("protocols.id", ondelete="SET NULL"))
    site: Mapped[str] = mapped_column(String(80), nullable=False, default="")

class RotationPreference807(Base):
    __tablename__ = "rotation_preferences807"
    __table_args__ = (
        CheckConstraint("route IN ('','subcutaneous','intramuscular','other')", name="ck_rotation807_route"),
        CheckConstraint("minimum_hours BETWEEN 0 AND 8760", name="ck_rotation807_interval"),
        CheckConstraint("recent_hours BETWEEN 0 AND 8760", name="ck_rotation807_recent"),
    )
    # Scope key is validated against the live scoped entities before writing.
    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    route: Mapped[str] = mapped_column(String(24), nullable=False)
    sequence_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    minimum_hours: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    recent_hours: Mapped[int] = mapped_column(Integer, nullable=False, default=72)

class SiteExclusion807(Base):
    __tablename__ = "site_exclusions807"
    site: Mapped[str] = mapped_column(String(80), primary_key=True)
    until_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    notes: Mapped[str] = mapped_column(Text, nullable=False, default="")

class GoalMilestonePreference807(Base):
    __tablename__ = "goal_milestone_preferences807"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    percentages_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
