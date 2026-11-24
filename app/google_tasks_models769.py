"""Release 769: additive, workspace-local Google Tasks synchronization state.

The private Tracker SQLite database is the only persisted token/link store.
No user data or OAuth secrets are committed to the source repository.
"""
from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base


class GoogleTasksConnection769(Base):
    __tablename__ = "google_tasks_connection769"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    refresh_token: Mapped[str] = mapped_column(Text, default="")
    oauth_state: Mapped[str] = mapped_column(String(160), default="")
    oauth_state_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    last_sync_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_error: Mapped[str] = mapped_column(String(160), default="")


class GoogleTasksList769(Base):
    __tablename__ = "google_tasks_lists769"
    kind: Mapped[str] = mapped_column(String(20), primary_key=True)
    list_id: Mapped[str] = mapped_column(String(160), nullable=False)


class GoogleTasksLink769(Base):
    __tablename__ = "google_tasks_links769"
    __table_args__ = (
        UniqueConstraint("list_id", "task_id", name="uq_google_task769"),
        Index("ix_google_task_source769", "kind", "source_id", "scheduled_on"),
    )
    key: Mapped[str] = mapped_column(String(180), primary_key=True)
    kind: Mapped[str] = mapped_column(String(20), nullable=False)
    source_id: Mapped[int] = mapped_column(Integer, nullable=False)
    scheduled_on: Mapped[date] = mapped_column(Date, nullable=False)
    scheduled_time: Mapped[str] = mapped_column(String(5), default="")
    list_id: Mapped[str] = mapped_column(String(160), nullable=False)
    task_id: Mapped[str] = mapped_column(String(160), nullable=False)
    last_status: Mapped[str] = mapped_column(String(20), default="needsAction")
    last_fingerprint: Mapped[str] = mapped_column(String(64), default="")
    imported_entry_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    removed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class GoogleTasksExclusion769(Base):
    __tablename__ = "google_tasks_exclusions769"
    __table_args__ = (UniqueConstraint("kind", "source_id", name="uq_google_exclusion769"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    kind: Mapped[str] = mapped_column(String(20), nullable=False)
    source_id: Mapped[int] = mapped_column(Integer, nullable=False)


class GoogleTasksTitle773(Base):
    """Optional Google-only shorthand, keyed to a Tracker schedule/item.

    Deliberately separate from the medical regimen and protocol models. A
    title update never changes the schedule, dose, date, or Google task ID.
    """
    __tablename__ = "google_tasks_titles773"
    __table_args__ = (
        UniqueConstraint("kind", "source_id", name="uq_google_tasks_title_source773"),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    kind: Mapped[str] = mapped_column(String(20), nullable=False)
    source_id: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(80), nullable=False)
