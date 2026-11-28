"""Non-exact reported lab measurements, isolated from numeric trend queries."""
from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column
from .db import Base

class LabTextResult808(Base):
    __tablename__ = "lab_text_results808"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    report_id: Mapped[int] = mapped_column(ForeignKey("lab_reports.id", ondelete="CASCADE"), index=True)
    analyte: Mapped[str] = mapped_column(String(120), nullable=False)
    value_text: Mapped[str] = mapped_column(String(80), nullable=False)
    unit: Mapped[str] = mapped_column(String(30), default="")
    printed_range: Mapped[str] = mapped_column(String(80), default="")
    flag: Mapped[str] = mapped_column(String(30), default="")
