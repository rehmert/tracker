"""Release 769: isolated synthetic Google Tasks calendar projection and sync.

Never touches real user data, installed DB, Google network, or OAuth secrets.
"""
from datetime import date, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base
from app.models import (Compound, Protocol, ProtocolItem, ProjectionExclusion,
                        RegimenEntry, RegimenItem, RegimenSchedule)
from app.google_tasks_models769 import (GoogleTasksConnection769,
                                        GoogleTasksLink769, GoogleTasksExclusion769)
from app.google_tasks_projection769 import projected769
from app import google_tasks_sync769 as sync


@pytest.fixture
def env(monkeypatch, tmp_path):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False},
                           poolclass=StaticPool)
    Base.metadata.create_all(engine)
    Factory = sessionmaker(bind=engine, expire_on_commit=False)
    with Factory() as db:
        med = RegimenItem(kind="medication", name="Synthetic Medicine", active=True)
        supp = RegimenItem(kind="supplement", name="Synthetic Vitamin", active=True)
        db.add_all([med, supp])
        db.flush()
        db.add_all([
            RegimenSchedule(item_id=med.id, cadence="daily", start_on=date(2026, 11, 24),
                            amount="1 tablet", active=True, at_time="07:30"),
            RegimenSchedule(item_id=supp.id, cadence="interval", interval_days=3,
                            start_on=date(2026, 11, 24), amount="1 capsule",
                            active=True, at_time="21:00"),
        ])
        compound = Compound(name="Synthetic Peptide", category="peptide")
        db.add(compound)
        db.flush()
        protocol = Protocol(name="Synthetic Protocol", is_active=True,
                            start_date=date(2026, 11, 24))
        db.add(protocol)
        db.flush()
        item = ProtocolItem(protocol_id=protocol.id, compound_id=compound.id,
                            position=0, amount_value=1.5, amount_unit="mg",
                            freq_count=3, freq_period="interval",
                            start_week=1, dose_time="20:00")
        db.add(item)
        db.add(GoogleTasksConnection769(id=1, enabled=True, refresh_token="synthetic-token"))
        db.commit()
    monkeypatch.setattr(sync, "SessionLocal", Factory)
    monkeypatch.setattr(sync, "configured769", lambda: ("synthetic-client", "secret", "uri"))
    monkeypatch.setattr(sync.config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(sync.config, "instance_label", lambda: "DEV")
    yield Factory
    engine.dispose()


def test_769_three_sources_and_dates_are_deterministic(env):
    with env() as db:
        rows = projected769(db, date(2026, 11, 24), 7)
        assert len([x for x in rows.values() if x.kind == "medication"]) == 7
        assert len([x for x in rows.values() if x.kind == "supplement"]) == 3
        assert len([x for x in rows.values() if x.kind == "protocol"]) == 3
        assert all(x.task_body()["due"].endswith("T00:00:00.000Z") for x in rows.values())
        assert all("Tracker ID: t769:" in x.task_body()["notes"] for x in rows.values())
        assert any(x.title.startswith("07:30") for x in rows.values())
        assert projected769(db, date(2026, 11, 24), 7) == rows


def test_769_prn_inactive_and_projection_exclusions_are_not_synced(env):
    with env() as db:
        schedule = db.get(RegimenSchedule, 2)
        schedule.cadence = "prn"
        item = db.get(ProtocolItem, 1)
        db.add(ProjectionExclusion(protocol_item_id=item.id,
                                   scheduled_on=date(2026, 11, 24), scope="once"))
        db.commit()
        projected = list(projected769(db, date(2026, 11, 24), 2).values())
        assert all(x.kind != "supplement" for x in projected)
        assert all(x.kind != "protocol" for x in projected)


def test_769_horizon_is_bounded(env):
    with env() as db:
        for days in (-1, 0, 15, 365, 2.5):
            with pytest.raises(ValueError):
                projected769(db, date(2026, 11, 24), days)


class FakeTasks:
    created = {}
    created_lists = {}
    def __init__(self, token):
        assert token == "synthetic-token"
    def close(self):
        pass
    def create_list(self, title):
        key = str(len(self.created_lists) + 1)
        self.created_lists[key] = title
        self.created[key] = {}
        return {"id": key, "title": title}
    def tasks(self, list_id):
        return list(self.created[list_id].values())
    def create_task(self, list_id, body):
        key = str(len(self.created[list_id]) + 1)
        task = dict(body, id=key)
        self.created[list_id][key] = task
        return task
    def patch_task(self, list_id, task_id, body):
        self.created[list_id][task_id].update(body)
        return dict(self.created[list_id][task_id])
    def delete_task(self, list_id, task_id):
        self.created[list_id][task_id]["deleted"] = True
        return {}


def test_769_repeated_sync_is_idempotent_and_imports_taken_only_once(env, monkeypatch):
    FakeTasks.created = {}
    FakeTasks.created_lists = {}
    monkeypatch.setattr(sync, "TasksClient769", FakeTasks)
    # Freeze the synthetic schedule window by patching projection to anchor
    # its date explicitly; no real personal dates or data.
    original = sync.projected769
    monkeypatch.setattr(sync, "projected769",
                        lambda db, today, days: original(db, date(2026, 11, 24), days))
    monkeypatch.setattr(sync, "date", SimpleNamespace(today=lambda:date(2026,11,24)))
    first = sync.sync_once769()
    assert first["created"] > 0
    assert sync.sync_once769()["created"] == 0
    with env() as db:
        link = db.scalar(select(GoogleTasksLink769).where(
            GoogleTasksLink769.kind == "medication",
            GoogleTasksLink769.scheduled_on == date(2026, 11, 24),
        ))
        remote = FakeTasks.created[link.list_id][link.task_id]
        remote["status"] = "completed"
        remote["completed"] = "2026-11-24T13:00:00.000Z"
    imported = sync.sync_once769()
    assert imported["imported"] == 1
    assert sync.sync_once769()["imported"] == 0
    with env() as db:
        records = list(db.scalars(select(RegimenEntry)))
        assert len(records) == 1
        assert records[0].outcome == "taken"
        assert records[0].schedule_id == 1
        assert records[0].notes.startswith("Google Tasks completion")


def test_769_protocol_completion_never_consumes_inventory(env, monkeypatch):
    FakeTasks.created = {}
    FakeTasks.created_lists = {}
    monkeypatch.setattr(sync, "TasksClient769", FakeTasks)
    original = sync.projected769
    monkeypatch.setattr(sync, "projected769",
                        lambda db, today, days: original(db, date(2026,11,24), days))
    monkeypatch.setattr(sync, "date", SimpleNamespace(today=lambda:date(2026,11,24)))
    sync.sync_once769()
    with env() as db:
        link = db.scalar(select(GoogleTasksLink769).where(
            GoogleTasksLink769.kind == "protocol"))
        FakeTasks.created[link.list_id][link.task_id]["status"] = "completed"
    result = sync.sync_once769()
    assert result["pending_protocols"] >= 1
    with env() as db:
        from app.models import DoseLog, BlendDose
        assert db.scalar(select(DoseLog)) is None
        assert db.scalar(select(BlendDose)) is None


def test_769_excluded_sources_do_not_generate_google_tasks(env, monkeypatch):
    FakeTasks.created = {}
    FakeTasks.created_lists = {}
    monkeypatch.setattr(sync, "TasksClient769", FakeTasks)
    original = sync.projected769
    monkeypatch.setattr(sync, "projected769",
                        lambda db, today, days: original(db, date(2026,11,24), days))
    monkeypatch.setattr(sync, "date", SimpleNamespace(today=lambda:date(2026,11,24)))
    with env() as db:
        db.add(GoogleTasksExclusion769(kind="medication", source_id=1))
        db.commit()
    sync.sync_once769()
    with env() as db:
        assert db.scalar(select(GoogleTasksLink769).where(
            GoogleTasksLink769.kind == "medication")) is None
