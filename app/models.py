from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (Boolean, CheckConstraint, Date, DateTime, Float, ForeignKey,
                        Integer, String, Text, func)
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
    coas: Mapped[list[Coa]] = relationship(back_populates="vial", cascade="all, delete-orphan",
                                           order_by="Coa.id.desc()")
    doses: Mapped[list[DoseLog]] = relationship(back_populates="vial")


class Coa(Base):
    """Certificate of analysis file plus the numbers transcribed from it."""
    __tablename__ = "coas"
    id: Mapped[int] = mapped_column(primary_key=True)
    vial_id: Mapped[int] = mapped_column(ForeignKey("vials.id", ondelete="CASCADE"))
    original_name: Mapped[str] = mapped_column(String(255))
    stored_name: Mapped[str] = mapped_column(String(80), unique=True)
    content_type: Mapped[str] = mapped_column(String(80))
    size_bytes: Mapped[int] = mapped_column(Integer)
    sha256: Mapped[str] = mapped_column(String(64))
    lab_name: Mapped[str] = mapped_column(String(160), default="")
    tested_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    purity_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    reported_content_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    reported_content_unit: Mapped[str | None] = mapped_column(String(8), nullable=True)
    notes: Mapped[str] = mapped_column(Text, default="")
    uploaded_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    vial: Mapped[Vial] = relationship(back_populates="coas")


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
