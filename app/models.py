from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (Boolean, CheckConstraint, Column, Date, DateTime, Float, ForeignKey,
                        Index, Integer, String, Table, Text, func)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base

VIAL_FORMS = ("lyophilized", "solution")
VIAL_STATUSES = ("sealed", "in_use", "finished", "discarded")
CATEGORIES = ("peptide", "testosterone", "other")


class Compound(Base):
    __tablename__ = "compounds"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True)
    category: Mapped[str] = mapped_column(String(30), default="peptide")
    notes: Mapped[str] = mapped_column(Text, default="")
    vials: Mapped[list[Vial]] = relationship(back_populates="compound")


class Purchase(Base):
    __tablename__ = "purchases"
    id: Mapped[int] = mapped_column(primary_key=True)
    vendor: Mapped[str] = mapped_column(String(160))
    purchased_on: Mapped[date] = mapped_column(Date)
    order_ref: Mapped[str] = mapped_column(String(120), default="")
    shipping_cents: Mapped[int] = mapped_column(Integer, default=0)
    tax_cents: Mapped[int] = mapped_column(Integer, default=0)
    discount_cents: Mapped[int] = mapped_column(Integer, default=0)
    notes: Mapped[str] = mapped_column(Text, default="")
    vials: Mapped[list[Vial]] = relationship(back_populates="purchase", order_by="Vial.id")
    supplies: Mapped[list[Supply]] = relationship("Supply", order_by="Supply.id")


class Vial(Base):
    """One physical vial. A kit of N vials is N rows sharing a purchase."""
    __tablename__ = "vials"
    __table_args__ = (
        CheckConstraint("content_value > 0", name="ck_vial_content_positive"),
        CheckConstraint("volume_ml IS NULL OR volume_ml > 0", name="ck_vial_volume_positive"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    compound_id: Mapped[int] = mapped_column(ForeignKey("compounds.id"))
    purchase_id: Mapped[int | None] = mapped_column(ForeignKey("purchases.id"), nullable=True)
    label: Mapped[str] = mapped_column(String(160), default="")
    lot: Mapped[str] = mapped_column(String(80), default="")
    cap_color: Mapped[str] = mapped_column(String(60), default="")
    kit_ref: Mapped[str] = mapped_column(String(120), default="")
    form: Mapped[str] = mapped_column(String(20), default="lyophilized")
    content_value: Mapped[float] = mapped_column(Float)          # label claim, whole vial
    content_unit: Mapped[str] = mapped_column(String(8))          # mcg | mg | g | IU
    volume_ml: Mapped[float | None] = mapped_column(Float, nullable=True)  # liquid / recon volume
    reconstituted_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    expires_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(12), default="sealed")
    use_coa_content: Mapped[bool] = mapped_column(Boolean, default=False)
    unit_price_cents: Mapped[int] = mapped_column(Integer, default=0)
    notes: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    compound: Mapped[Compound] = relationship(back_populates="vials")
    purchase: Mapped[Purchase | None] = relationship(back_populates="vials")

    doses: Mapped[list[DoseLog]] = relationship(back_populates="vial")

    coa_id: Mapped[int | None] = mapped_column(ForeignKey("coas.id", ondelete="SET NULL"), nullable=True, index=True)
    coa: Mapped["Coa | None"] = relationship("Coa", back_populates="vials")


class Coa(Base):
    """Certificate of analysis file plus the numbers transcribed from it."""
    __tablename__ = "coas"
    id: Mapped[int] = mapped_column(primary_key=True)
    original_name: Mapped[str] = mapped_column(String(255), default="")
    stored_name: Mapped[str | None] = mapped_column(String(80), unique=True, nullable=True)
    content_type: Mapped[str] = mapped_column(String(80), default="")
    size_bytes: Mapped[int] = mapped_column(Integer, default=0)
    sha256: Mapped[str] = mapped_column(String(64), default="")
    lab_name: Mapped[str] = mapped_column(String(160), default="")
    tested_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    purity_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    endotoxin_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    job_id: Mapped[str] = mapped_column(String(120), default="")
    verify_code: Mapped[str] = mapped_column(String(120), default="")
    reported_content_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    reported_content_unit: Mapped[str | None] = mapped_column(String(8), nullable=True)
    notes: Mapped[str] = mapped_column(Text, default="")
    uploaded_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    vials: Mapped[list["Vial"]] = relationship("Vial", back_populates="coa")


class Supply(Base):
    __tablename__ = "supplies"
    id: Mapped[int] = mapped_column(primary_key=True)
    purchase_id: Mapped[int] = mapped_column(ForeignKey("purchases.id"))
    compound_id: Mapped[int | None] = mapped_column(ForeignKey("compounds.id"), nullable=True)
    name: Mapped[str] = mapped_column(String(160))
    kind: Mapped[str] = mapped_column(String(20))  # bac_water | pill
    purchased_qty: Mapped[float] = mapped_column(Float)
    remaining_qty: Mapped[float] = mapped_column(Float)
    unit_price_cents: Mapped[int] = mapped_column(Integer, default=0)
    notes: Mapped[str] = mapped_column(Text, default="")


class SupplyUsage(Base):
    __tablename__ = "supply_usages"
    id: Mapped[int] = mapped_column(primary_key=True)
    supply_id: Mapped[int] = mapped_column(ForeignKey("supplies.id"))
    vial_id: Mapped[int | None] = mapped_column(ForeignKey("vials.id"), nullable=True)
    dose_id: Mapped[int | None] = mapped_column(ForeignKey("dose_logs.id"), nullable=True)
    amount: Mapped[float] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class DoseLog(Base):
    """A logged administration (kind='dose') or discarded amount (kind='waste')."""
    __tablename__ = "dose_logs"
    id: Mapped[int] = mapped_column(primary_key=True)
    vial_id: Mapped[int] = mapped_column(ForeignKey("vials.id"))
    taken_at: Mapped[datetime] = mapped_column(DateTime)
    entered_value: Mapped[float] = mapped_column(Float)
    entered_unit: Mapped[str] = mapped_column(String(8))
    amount_base: Mapped[float] = mapped_column(Float)   # mcg or IU, as the vial is tracked
    kind: Mapped[str] = mapped_column(String(8), default="dose")
    site: Mapped[str] = mapped_column(String(80), default="")
    notes: Mapped[str] = mapped_column(Text, default="")
    vial: Mapped[Vial] = relationship(back_populates="doses")


class Protocol(Base):
    """A saved what-if plan. It never changes inventory by itself."""
    __tablename__ = "protocols"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(160))
    is_active: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    notes: Mapped[str] = mapped_column(Text, default="")
    horizon_weeks: Mapped[float] = mapped_column(Float, default=12)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(),
                                                 onupdate=func.now())
    items: Mapped[list[ProtocolItem]] = relationship(
        back_populates="protocol", cascade="all, delete-orphan", order_by="ProtocolItem.position")


class ProtocolItem(Base):
    __tablename__ = "protocol_items"
    id: Mapped[int] = mapped_column(primary_key=True)
    protocol_id: Mapped[int] = mapped_column(ForeignKey("protocols.id", ondelete="CASCADE"))
    compound_id: Mapped[int] = mapped_column(ForeignKey("compounds.id"))
    position: Mapped[int] = mapped_column(Integer, default=0)
    amount_value: Mapped[float] = mapped_column(Float)
    amount_unit: Mapped[str] = mapped_column(String(8))
    freq_count: Mapped[float] = mapped_column(Float)
    freq_period: Mapped[str] = mapped_column(String(10))  # day | week | month | interval
    protocol: Mapped[Protocol] = relationship(back_populates="items")
    compound: Mapped[Compound] = relationship()


class PkScenario(Base):
    """Hypothetical schedule; never alters dose logs or inventory."""
    __tablename__ = "pk_scenarios"
    id: Mapped[int] = mapped_column(primary_key=True)
    compound_id: Mapped[int] = mapped_column(ForeignKey("compounds.id"))
    name: Mapped[str] = mapped_column(String(160))
    half_life_hours: Mapped[float] = mapped_column(Float)
    absorption_half_life_hours: Mapped[float] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    compound: Mapped[Compound] = relationship()
    doses: Mapped[list["PkPlannedDose"]] = relationship(
        back_populates="scenario", cascade="all, delete-orphan")


class PkPlannedDose(Base):
    __tablename__ = "pk_planned_doses"
    id: Mapped[int] = mapped_column(primary_key=True)
    scenario_id: Mapped[int] = mapped_column(ForeignKey("pk_scenarios.id", ondelete="CASCADE"))
    planned_at: Mapped[datetime] = mapped_column(DateTime)
    amount_mg: Mapped[float] = mapped_column(Float)
    scenario: Mapped[PkScenario] = relationship(back_populates="doses")


class VitalReading(Base):
    """One sitting: any mix of weight (stored in kg), blood pressure and pulse."""
    __tablename__ = "vital_readings"
    __table_args__ = (
        CheckConstraint("weight_kg IS NOT NULL OR systolic IS NOT NULL OR pulse_bpm IS NOT NULL",
                        name="ck_reading_has_value"),
        Index("ix_vital_readings_time", "measured_at"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    measured_at: Mapped[datetime] = mapped_column(DateTime)
    weight_kg: Mapped[float | None] = mapped_column(Float, nullable=True)
    systolic: Mapped[int | None] = mapped_column(Integer, nullable=True)
    diastolic: Mapped[int | None] = mapped_column(Integer, nullable=True)
    pulse_bpm: Mapped[int | None] = mapped_column(Integer, nullable=True)
    context: Mapped[str] = mapped_column(String(80), default="")   # e.g. "morning, seated"
    notes: Mapped[str] = mapped_column(Text, default="")


page_compounds = Table(
    "page_compounds", Base.metadata,
    Column("page_id", ForeignKey("pages.id", ondelete="CASCADE"), primary_key=True),
    Column("compound_id", ForeignKey("compounds.id", ondelete="CASCADE"), primary_key=True),
)

SOURCE_KINDS = ("web", "book", "paper", "other")


class Page(Base):
    """A free-text note. Body is markdown-style text; [[Title]] links to other pages."""
    __tablename__ = "pages"
    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(200), unique=True)
    body: Mapped[str] = mapped_column(Text, default="")
    tags: Mapped[str] = mapped_column(String(400), default="")      # comma separated, lower case
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(),
                                                 onupdate=func.now())
    sources: Mapped[list[Source]] = relationship(
        back_populates="page", cascade="all, delete-orphan", order_by="Source.id")
    compounds: Mapped[list[Compound]] = relationship(secondary=page_compounds)

    @property
    def tag_list(self) -> list[str]:
        return [t for t in self.tags.split(",") if t]


class Source(Base):
    """Where a piece of information came from: a link, a book, a paper."""
    __tablename__ = "sources"
    id: Mapped[int] = mapped_column(primary_key=True)
    page_id: Mapped[int] = mapped_column(ForeignKey("pages.id", ondelete="CASCADE"))
    kind: Mapped[str] = mapped_column(String(10), default="web")
    title: Mapped[str] = mapped_column(String(300), default="")
    url: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    author: Mapped[str] = mapped_column(String(200), default="")
    publication: Mapped[str] = mapped_column(String(200), default="")  # site, journal, publisher
    location: Mapped[str] = mapped_column(String(120), default="")     # chapter / page / DOI
    accessed_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    note: Mapped[str] = mapped_column(Text, default="")
    page: Mapped[Page] = relationship(back_populates="sources")


class LabReport(Base):
    """One blood draw / lab report, with an optional copy of the report file."""
    __tablename__ = "lab_reports"
    id: Mapped[int] = mapped_column(primary_key=True)
    drawn_on: Mapped[date] = mapped_column(Date)
    lab_name: Mapped[str] = mapped_column(String(160), default="")
    notes: Mapped[str] = mapped_column(Text, default="")
    original_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    stored_name: Mapped[str | None] = mapped_column(String(80), nullable=True, unique=True)
    content_type: Mapped[str | None] = mapped_column(String(80), nullable=True)
    size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    results: Mapped[list[LabResult]] = relationship(
        back_populates="report", cascade="all, delete-orphan", order_by="LabResult.id")


class LabResult(Base):
    """One analyte value. ref_low / ref_high are the range PRINTED on the report."""
    __tablename__ = "lab_results"
    id: Mapped[int] = mapped_column(primary_key=True)
    report_id: Mapped[int] = mapped_column(ForeignKey("lab_reports.id", ondelete="CASCADE"))
    analyte: Mapped[str] = mapped_column(String(120))
    value: Mapped[float] = mapped_column(Float)
    unit: Mapped[str] = mapped_column(String(30))
    ref_low: Mapped[float | None] = mapped_column(Float, nullable=True)
    ref_high: Mapped[float | None] = mapped_column(Float, nullable=True)
    note: Mapped[str] = mapped_column(String(300), default="")
    report: Mapped[LabReport] = relationship(back_populates="results")
