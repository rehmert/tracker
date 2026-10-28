from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (Boolean, CheckConstraint, Column, Date, DateTime, Float, ForeignKey,
                        Index, Integer, String, Table, Text, func)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base

coa_vial_links = Table(
    "coa_vial_links", Base.metadata,
    Column("coa_id", ForeignKey("coas.id", ondelete="CASCADE"), primary_key=True),
    Column("vial_id", ForeignKey("vials.id", ondelete="CASCADE"), primary_key=True),
)

VIAL_FORMS = ("lyophilized", "solution")
VIAL_STATUSES = ("sealed", "in_use", "finished", "discarded")
CATEGORIES = ("peptide", "testosterone", "other")


class Compound(Base):
    __tablename__ = "compounds"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True)
    category: Mapped[str] = mapped_column(String(30), default="peptide")
    notes: Mapped[str] = mapped_column(Text, default="")
    primary_unit: Mapped[str] = mapped_column(String(8), default="mg", server_default="mg")
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
    received_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    first_punctured_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    first_dosed_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    beyond_use_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    closed_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    storage_notes: Mapped[str] = mapped_column(Text, default="")
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
    linked_coas: Mapped[list["Coa"]] = relationship("Coa", secondary="coa_vial_links", back_populates="linked_vials")

    @property
    def all_coas(self):
        return sorted({c.id: c for c in ([self.coa] if self.coa else []) + list(self.linked_coas)}.values(), key=lambda c: (c.tested_on or date.min, c.id), reverse=True)
    linked_coas: Mapped[list["Coa"]] = relationship("Coa", secondary="coa_vial_links", back_populates="linked_vials")

    @property
    def all_coas(self):
        return sorted({c.id: c for c in ([self.coa] if self.coa else []) + list(self.linked_coas)}.values(), key=lambda c: (c.tested_on or date.min, c.id), reverse=True)


class Blend(Base):
    """One physical mixed vial; separate from single-compound Vial records."""
    __tablename__ = "blends"
    id: Mapped[int] = mapped_column(primary_key=True)
    label: Mapped[str] = mapped_column(String(160), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    final_volume_ml: Mapped[float] = mapped_column(Float, nullable=False)
    diluent_ml: Mapped[float] = mapped_column(Float, default=0)
    capacity_ml: Mapped[float | None] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(String(12), default="in_use")
    notes: Mapped[str] = mapped_column(Text, default="")
    components: Mapped[list["BlendComponent"]] = relationship(back_populates="blend", cascade="all, delete-orphan")
    doses: Mapped[list["BlendDose"]] = relationship(back_populates="blend", cascade="all, delete-orphan")


class BlendComponent(Base):
    __tablename__ = "blend_components"
    id: Mapped[int] = mapped_column(primary_key=True)
    blend_id: Mapped[int] = mapped_column(ForeignKey("blends.id"), nullable=False, index=True)
    source_vial_id: Mapped[int] = mapped_column(ForeignKey("vials.id"), nullable=False, index=True)
    compound_id: Mapped[int] = mapped_column(ForeignKey("compounds.id"), nullable=False)
    transferred_base: Mapped[float] = mapped_column(Float, nullable=False)
    transferred_ml: Mapped[float] = mapped_column(Float, nullable=False)
    target_dose_base: Mapped[float] = mapped_column(Float, nullable=False)
    target_unit: Mapped[str] = mapped_column(String(8), nullable=False)
    blend: Mapped[Blend] = relationship(back_populates="components")
    source_vial: Mapped[Vial] = relationship()
    compound: Mapped[Compound] = relationship()


class BlendDose(Base):
    __tablename__ = "blend_doses"
    id: Mapped[int] = mapped_column(primary_key=True)
    blend_id: Mapped[int] = mapped_column(ForeignKey("blends.id"), nullable=False, index=True)
    taken_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    volume_ml: Mapped[float] = mapped_column(Float, nullable=False)
    kind: Mapped[str] = mapped_column(String(8), default="dose")
    notes: Mapped[str] = mapped_column(Text, default="")
    blend: Mapped[Blend] = relationship(back_populates="doses")


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
    verification_status: Mapped[str] = mapped_column(String(20), default="unreviewed", server_default="unreviewed")
    verification_notes: Mapped[str] = mapped_column(Text, default="", server_default="")
    verified_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    vials: Mapped[list["Vial"]] = relationship("Vial", back_populates="coa")
    linked_vials: Mapped[list["Vial"]] = relationship("Vial", secondary="coa_vial_links", back_populates="linked_coas")

    @property
    def all_vials(self):
        return sorted({v.id: v for v in list(self.vials) + list(self.linked_vials)}.values(), key=lambda v: v.id)
    linked_vials: Mapped[list["Vial"]] = relationship("Vial", secondary="coa_vial_links", back_populates="linked_coas")

    @property
    def all_vials(self):
        return sorted({v.id: v for v in list(self.vials) + list(self.linked_vials)}.values(), key=lambda v: v.id)


class CoaRevision(Base):
    """Immutable snapshot of a COA before an edit or status change."""
    __tablename__ = "coa_revisions"
    id: Mapped[int] = mapped_column(primary_key=True)
    coa_id: Mapped[int | None] = mapped_column(ForeignKey("coas.id", ondelete="SET NULL"), nullable=True, index=True)
    event: Mapped[str] = mapped_column(String(40), nullable=False)
    snapshot_json: Mapped[str] = mapped_column(Text, nullable=False)
    changed_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class SupplyCategory(Base):
    """User-defined supply categories. Built-ins are seeded on first use."""
    __tablename__ = "supply_categories"
    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    label: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    unit: Mapped[str] = mapped_column(String(24), default="count")


class SupplyProduct(Base):
    """Reusable defaults for purchasing consumables; inventory remains on Supply."""
    __tablename__ = "supply_products"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    kind: Mapped[str] = mapped_column(String(20), nullable=False)
    package_type: Mapped[str] = mapped_column(String(30), default="box")
    units_per_pack: Mapped[float] = mapped_column(Float, default=1)
    last_line_price_cents: Mapped[int] = mapped_column(Integer, default=0)
    preferred_vendor: Mapped[str] = mapped_column(String(160), default="")


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
    bulk_pack_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    bulk_units_per_pack: Mapped[float | None] = mapped_column(Float, nullable=True)
    bulk_total_cents: Mapped[int | None] = mapped_column(Integer, nullable=True)
    notes: Mapped[str] = mapped_column(Text, default="")


class SupplyUsage(Base):
    __tablename__ = "supply_usages"
    id: Mapped[int] = mapped_column(primary_key=True)
    supply_id: Mapped[int] = mapped_column(ForeignKey("supplies.id"))
    vial_id: Mapped[int | None] = mapped_column(ForeignKey("vials.id"), nullable=True)
    dose_id: Mapped[int | None] = mapped_column(ForeignKey("dose_logs.id"), nullable=True)
    amount: Mapped[float] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class PreparationEvent(Base):
    """A user-recorded preparation/filtering event, independent of dosing."""
    __tablename__ = "preparation_events"
    id: Mapped[int] = mapped_column(primary_key=True)
    vial_id: Mapped[int] = mapped_column(ForeignKey("vials.id"))
    kind: Mapped[str] = mapped_column(String(20))  # reconstitution | filtering
    occurred_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    notes: Mapped[str] = mapped_column(Text, default="")


class PreparationSupply(Base):
    __tablename__ = "preparation_supplies"
    id: Mapped[int] = mapped_column(primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("preparation_events.id"))
    usage_id: Mapped[int] = mapped_column(ForeignKey("supply_usages.id"))


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
    start_week: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    end_week: Mapped[int | None] = mapped_column(Integer, nullable=True)
    dose_days: Mapped[str] = mapped_column(String(30), default="", server_default="")
    dose_time: Mapped[str] = mapped_column(String(5), default="", server_default="")
    fasting_hours: Mapped[float | None] = mapped_column(Float, nullable=True)
    protocol: Mapped[Protocol] = relationship(back_populates="items")
    compound: Mapped[Compound] = relationship()


class ProjectionExclusion(Base):
    """Suppress a projected protocol-item occurrence, never an actual DoseLog."""
    __tablename__ = "projection_exclusions"
    __table_args__ = (Index("ix_projection_exclusions_item_date", "protocol_item_id", "scheduled_on"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    protocol_item_id: Mapped[int] = mapped_column(ForeignKey("protocol_items.id", ondelete="CASCADE"), index=True)
    scheduled_on: Mapped[date] = mapped_column(Date)
    scope: Mapped[str] = mapped_column(String(12))  # once | onward
    reason: Mapped[str] = mapped_column(String(255), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    item: Mapped[ProtocolItem] = relationship()


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


class InventoryAdjustment(Base):
    __tablename__ = "inventory_adjustments"
    id: Mapped[int] = mapped_column(primary_key=True)
    supply_id: Mapped[int] = mapped_column(ForeignKey("supplies.id"), nullable=False)
    previous_qty: Mapped[float] = mapped_column(Float, nullable=False)
    counted_qty: Mapped[float] = mapped_column(Float, nullable=False)
    reason: Mapped[str] = mapped_column(String(240), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class ChangeAudit(Base):
    __tablename__ = "change_audit"
    id: Mapped[int] = mapped_column(primary_key=True)
    entity_type: Mapped[str] = mapped_column(String(40), nullable=False)
    entity_id: Mapped[int] = mapped_column(Integer, nullable=False)
    action: Mapped[str] = mapped_column(String(40), nullable=False)
    before_json: Mapped[str] = mapped_column(Text, default="{}")
    after_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class ProtocolRevision(Base):
    __tablename__ = "protocol_revisions"
    id: Mapped[int] = mapped_column(primary_key=True)
    protocol_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    revision: Mapped[int] = mapped_column(Integer, nullable=False)
    snapshot_json: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class VendorPriceSheet(Base):
    __tablename__ = "vendor_price_sheets"
    id: Mapped[int] = mapped_column(primary_key=True)
    vendor: Mapped[str] = mapped_column(String(160))
    name: Mapped[str] = mapped_column(String(160), default="")
    imported_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    entries: Mapped[list["VendorPriceEntry"]] = relationship(back_populates="sheet", cascade="all, delete-orphan")

class VendorPriceEntry(Base):
    __tablename__ = "vendor_price_entries"
    id: Mapped[int] = mapped_column(primary_key=True)
    sheet_id: Mapped[int] = mapped_column(ForeignKey("vendor_price_sheets.id", ondelete="CASCADE"))
    item_name: Mapped[str] = mapped_column(String(200))
    strength: Mapped[str] = mapped_column(String(80), default="")
    package: Mapped[str] = mapped_column(String(80), default="")
    vial_count: Mapped[int] = mapped_column(Integer, default=1)
    total_price_cents: Mapped[int] = mapped_column(Integer)
    sheet: Mapped["VendorPriceSheet"] = relationship(back_populates="entries")
    @property
    def per_vial_cents(self):
        return self.total_price_cents / self.vial_count
