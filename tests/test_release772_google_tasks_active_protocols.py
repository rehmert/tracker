"""Release 772 — active protocol visibility and sync eligibility.

Uses synthetic local SQLite only, with no Google network, user information or installed data.
"""
from datetime import date

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base
from app.models import Compound, Protocol, ProtocolItem, RegimenItem, RegimenSchedule
from app.google_tasks_projection769 import projected769
from app.routers import google_tasks769


@pytest.fixture
def sessions():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory() as db:
        compound = Compound(name="Synthetic Compound", category="peptide")
        regimen = RegimenItem(kind="supplement", name="Synthetic Vitamin", active=True)
        db.add_all([compound, regimen])
        db.flush()
        db.add(RegimenSchedule(
            item_id=regimen.id, cadence="daily", start_on=date(2026, 11, 24),
            amount="1 capsule", active=True, at_time="07:30",
        ))
        for name, active in (
            ("Active synthetic protocol", True),
            ("Inactive synthetic protocol", False),
            ("What-if synthetic protocol", False),
        ):
            protocol = Protocol(
                name=name, is_active=active, start_date=date(2026, 11, 24),
            )
            db.add(protocol)
            db.flush()
            db.add(ProtocolItem(
                protocol_id=protocol.id, compound_id=compound.id,
                position=0, amount_value=1.5, amount_unit="mg",
                freq_count=1, freq_period="interval", start_week=1,
                dose_time="20:00",
            ))
        db.commit()
    yield factory
    engine.dispose()


@pytest.fixture
def mock_ui(monkeypatch):
    monkeypatch.setattr(
        google_tasks769, "render",
        lambda request, template, **context: context,
    )
    monkeypatch.setattr(
        google_tasks769.config, "instance_label", lambda: "DEV",
    )


def test_772_google_settings_only_show_active_protocols(sessions, mock_ui):
    with sessions() as db:
        context = google_tasks769.settings769(None, db)
        protocols = [s for s in context["sources"] if s["kind"] == "protocol"]
        assert len(protocols) == 1
        assert protocols[0]["name"].startswith("Active synthetic protocol /")
        assert protocols[0]["active"]
        assert not any(
            "Inactive synthetic protocol" in row["name"] or
            "What-if synthetic protocol" in row["name"]
            for row in context["sources"]
        )
        assert any(row["kind"] == "supplement" for row in context["sources"])


def test_772_activation_switches_settings_and_task_projection(sessions, mock_ui):
    with sessions() as db:
        before = projected769(db, date(2026, 11, 24), 2)
        protocol_notes = [row.notes for row in before.values() if row.kind == "protocol"]
        assert protocol_notes
        assert all("Active synthetic protocol" in note for note in protocol_notes)
        active = db.scalar(select(Protocol).where(
            Protocol.name == "Active synthetic protocol",
        ))
        inactive = db.scalar(select(Protocol).where(
            Protocol.name == "Inactive synthetic protocol",
        ))
        active.is_active = False
        inactive.is_active = True
        db.commit()
        sources = google_tasks769.settings769(None, db)["sources"]
        shown = [row["name"] for row in sources if row["kind"] == "protocol"]
        assert len(shown) == 1
        assert shown[0].startswith("Inactive synthetic protocol /")
        after = projected769(db, date(2026, 11, 24), 2)
        notes = [row.notes for row in after.values() if row.kind == "protocol"]
        assert notes
        assert all("Inactive synthetic protocol" in note for note in notes)
        assert not any("What-if synthetic protocol" in note for note in notes)
