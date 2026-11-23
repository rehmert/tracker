"""Release 762 additive, workspace-scoped progress measurements.

Every table is owned by the existing authenticated workspace database. These
models register with Base during app startup; no existing table is modified.
"""
from datetime import date
from sqlalchemy import Date, Float, Integer, String, Text, CheckConstraint, Index
from sqlalchemy.orm import Mapped, mapped_column
from .db import Base

MEASURES762 = {
    "waist_navel": ("Waist · navel", 30, 250),
    "waist_narrow": ("Waist · narrowest", 30, 250),
    "hip": ("Hips", 30, 250),
    "chest": ("Chest", 30, 250),
    "neck": ("Neck", 15, 100),
    "arm_left": ("Left upper arm", 10, 100),
    "arm_right": ("Right upper arm", 10, 100),
    "thigh_left": ("Left thigh", 10, 150),
    "thigh_right": ("Right thigh", 10, 150),
    "calf_left": ("Left calf", 10, 100),
    "calf_right": ("Right calf", 10, 100),
}
COMPOSITION762 = {
    "body_fat_pct": ("Body-fat %", 0, 80),
    "fat_mass_kg": ("Estimated fat mass", 0, 300),
    "fat_free_mass_kg": ("Estimated fat-free mass", 0, 300),
    "skeletal_muscle_kg": ("Estimated skeletal muscle mass", 0, 300),
    "visceral_fat": ("Visceral fat estimate/rating", 0, 1000),
}
FREQUENCIES762 = {
    "weight": 1, "waist": 7, "other": 21, "strength": 0,
    "bia": 21, "photos": 30, "dexa": 150, "labs": 0,
}

class ProgressSettings762(Base):
    __tablename__ = "progress_settings762"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    height_cm: Mapped[float | None] = mapped_column(Float, nullable=True)
    starting_weight_kg: Mapped[float | None] = mapped_column(Float, nullable=True)
    goal_weight_kg: Mapped[float | None] = mapped_column(Float, nullable=True)
    measurement_unit: Mapped[str] = mapped_column(String(3), default="in")
    frequencies_json: Mapped[str] = mapped_column(Text, default="{}")

class ProgressMeasure762(Base):
    __tablename__ = "progress_measurements762"
    __table_args__ = (Index("ix_progress_measure762_date", "measured_on"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    measured_on: Mapped[date] = mapped_column(Date, nullable=False)
    waist_navel: Mapped[float | None] = mapped_column(Float)
    waist_narrow: Mapped[float | None] = mapped_column(Float)
    hip: Mapped[float | None] = mapped_column(Float)
    chest: Mapped[float | None] = mapped_column(Float)
    neck: Mapped[float | None] = mapped_column(Float)
    arm_left: Mapped[float | None] = mapped_column(Float)
    arm_right: Mapped[float | None] = mapped_column(Float)
    thigh_left: Mapped[float | None] = mapped_column(Float)
    thigh_right: Mapped[float | None] = mapped_column(Float)
    calf_left: Mapped[float | None] = mapped_column(Float)
    calf_right: Mapped[float | None] = mapped_column(Float)
    notes: Mapped[str] = mapped_column(Text, default="")

class ProgressComposition762(Base):
    __tablename__ = "progress_composition762"
    __table_args__ = (
        CheckConstraint("method IN ('BIA','DEXA','other')", name="ck_progress762_method"),
        Index("ix_progress_composition762_date", "measured_on"),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    measured_on: Mapped[date] = mapped_column(Date, nullable=False)
    method: Mapped[str] = mapped_column(String(12), nullable=False)
    device: Mapped[str] = mapped_column(String(160), default="")
    body_fat_pct: Mapped[float | None] = mapped_column(Float)
    fat_mass_kg: Mapped[float | None] = mapped_column(Float)
    fat_free_mass_kg: Mapped[float | None] = mapped_column(Float)
    skeletal_muscle_kg: Mapped[float | None] = mapped_column(Float)
    visceral_fat: Mapped[float | None] = mapped_column(Float)
    segmental_notes: Mapped[str] = mapped_column(Text, default="")
    conditions: Mapped[str] = mapped_column(Text, default="")

class ProgressFunction762(Base):
    __tablename__ = "progress_function762"
    __table_args__ = (Index("ix_progress_function762_date", "measured_on"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    measured_on: Mapped[date] = mapped_column(Date, nullable=False)
    knee_pain: Mapped[int | None] = mapped_column(Integer)
    shoulder_pain: Mapped[int | None] = mapped_column(Integer)
    walking_minutes: Mapped[float | None] = mapped_column(Float)
    walking_distance_km: Mapped[float | None] = mapped_column(Float)
    sit_to_stand_reps: Mapped[int | None] = mapped_column(Integer)
    recovery: Mapped[int | None] = mapped_column(Integer)
    notes: Mapped[str] = mapped_column(Text, default="")

class ProgressMarker762(Base):
    __tablename__ = "progress_markers762"
    __table_args__ = (Index("ix_progress_markers762_date", "measured_on"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    measured_on: Mapped[date] = mapped_column(Date, nullable=False)
    category: Mapped[str] = mapped_column(String(24), nullable=False)
    label: Mapped[str] = mapped_column(String(160), nullable=False)
    notes: Mapped[str] = mapped_column(Text, default="")
