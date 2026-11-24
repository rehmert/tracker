"""Release 773: isolated Google Tasks custom-title lifecycle and safe reconciliation.

All records and HTTP clients are synthetic. Never uses real OAuth, Google,
installed Tracker databases or user medications.
"""
from datetime import date
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base
from app.models import Compound, Protocol, ProtocolItem, RegimenItem, RegimenSchedule
from app.google_tasks_models769 import GoogleTasksConnection769, GoogleTasksTitle773, GoogleTasksLink769
from app.google_tasks_projection769 import projected769
from app.routers import google_tasks769 as router
from app import google_tasks_sync769 as sync


@pytest.fixture
def env(monkeypatch, tmp_path):
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory() as db:
        med = RegimenItem(kind="medication", name="Synthetic Detailed Medication", active=True)
        supp = RegimenItem(kind="supplement", name="Synthetic Long Vitamin Description", active=True)
        db.add_all([med, supp])
        db.flush()
        db.add_all([
            RegimenSchedule(item_id=med.id, cadence="daily",
                            start_on=date(2026,11,24), amount="1 tablet",
                            at_time="07:30", active=True),
            RegimenSchedule(item_id=supp.id, cadence="daily",
                            start_on=date(2026,11,24), amount="1 capsule",
                            at_time="21:00", active=True),
        ])
        compound = Compound(name="Synthetic Compound Full Name", category="peptide")
        db.add(compound)
        db.flush()
        protocol = Protocol(name="Synthetic Active Protocol", is_active=True,
                            start_date=date(2026,11,24))
        inactive = Protocol(name="Synthetic What-if Protocol", is_active=False,
                            start_date=date(2026,11,24))
        db.add_all([protocol, inactive])
        db.flush()
        db.add_all([
            ProtocolItem(protocol_id=protocol.id, compound_id=compound.id,
                         position=0, amount_value=1.5, amount_unit="mg",
                         freq_count=1, freq_period="interval", start_week=1,
                         dose_time="20:00"),
            ProtocolItem(protocol_id=inactive.id, compound_id=compound.id,
                         position=0, amount_value=2, amount_unit="mg",
                         freq_count=1, freq_period="interval", start_week=1,
                         dose_time="20:00"),
        ])
        db.add(GoogleTasksConnection769(
            id=1, enabled=True, refresh_token="synthetic-test-token",
        ))
        db.commit()
    monkeypatch.setattr(router, "render", lambda request, template, **kw: kw)
    monkeypatch.setattr(sync, "SessionLocal", factory)
    monkeypatch.setattr(sync, "configured769", lambda: ("synthetic", "secret", "callback"))
    monkeypatch.setattr(sync.config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(sync.config, "instance_label", lambda: "DEV")
    yield factory
    engine.dispose()


def records_for_day(db):
    return [o for o in projected769(db, date(2026,11,24), 1).values()]


def test_773_default_titles_unmodified_and_ui_empty(env):
    with env() as db:
        rows = records_for_day(db)
        assert len(rows) == 3
        assert any(x.title == "07:30 · Synthetic Detailed Medication — 1 tablet" for x in rows)
        assert any(x.title == "21:00 · Synthetic Long Vitamin Description — 1 capsule" for x in rows)
        assert any(x.title == "20:00 · Synthetic Compound Full Name — 1.5 mg" for x in rows)
        context = router.settings769(None, db)
        assert len([r for r in context["sources"] if r["kind"] == "protocol"]) == 1
        assert all(s["custom_title"] == "" for s in context["sources"])


def test_773_save_three_custom_titles_and_preserve_full_details_in_notes(env):
    with env() as db:
        for kind, source_id, title in [
            ("medication", 1, "Med"),
            ("supplement", 2, "  Vitamin   D  "),
            ("protocol", 1, "HGH"),
        ]:
            result = router.update_title773(kind, source_id, title, db)
            assert result.status_code == 303
        rows = records_for_day(db)
        assert sorted(x.title for x in rows) == sorted([
            "07:30 · Med", "21:00 · Vitamin D", "20:00 · HGH",
        ])
        for o in rows:
            notes = o.task_body()["notes"]
            assert "Tracker ID: t769:" in notes
            assert "scheduled amount:" in notes
            assert "Synthetic " in notes
        assert db.scalar(select(GoogleTasksTitle773).where(
            GoogleTasksTitle773.kind=="supplement")).title == "Vitamin D"
        shown = router.settings769(None, db)["sources"]
        assert {row["kind"]:row["custom_title"] for row in shown} == {
            "medication":"Med", "supplement":"Vitamin D", "protocol":"HGH",
        }


def test_773_clear_custom_title_restores_default_and_does_not_erase_tracker_name(env):
    with env() as db:
        router.update_title773("medication", 1, "Med", db)
        router.update_title773("medication", 1, " ", db)
        assert db.scalar(select(GoogleTasksTitle773)) is None
        assert records_for_day(db)[0].title.startswith("07:30 · Synthetic Detailed Medication")
        assert db.get(RegimenItem, 1).name == "Synthetic Detailed Medication"


@pytest.mark.parametrize("kind,source_id", [
    ("invalid",1),("medication",0),("medication",999),
    ("medication",2),("protocol",999),("protocol",2),
])
def test_773_no_mutation_of_unknown_or_inactive_source(env, kind, source_id):
    with env() as db:
        with pytest.raises(HTTPException) as exc:
            router.update_title773(kind, source_id, "Test", db)
        assert exc.value.status_code == 404
        assert db.scalar(select(GoogleTasksTitle773)) is None


@pytest.mark.parametrize("bad", ["X" * 81, "one\nother", "bad\x7ftitle", "abc\ttitle"])
def test_773_reject_long_or_control_character_titles(env, bad):
    with env() as db:
        with pytest.raises(HTTPException) as exc:
            router.update_title773("medication", 1, bad, db)
        assert exc.value.status_code == 400
        assert db.scalar(select(GoogleTasksTitle773)) is None


class FakeTasks:
    lists_by_id = {}
    names = {}
    writes = 0

    def __init__(self, token):
        assert token == "synthetic-test-token"

    def close(self): pass

    def create_list(self, title):
        ident = str(len(self.names) + 1)
        self.names[ident] = title
        self.lists_by_id[ident] = {}
        return {"id":ident}

    def tasks(self, list_id):
        return list(self.lists_by_id[list_id].values())

    def create_task(self, list_id, body):
        ident = str(len(self.lists_by_id[list_id]) + 1)
        value = dict(body, id=ident)
        self.lists_by_id[list_id][ident] = value
        self.writes += 1
        return value

    def patch_task(self, list_id, task_id, body):
        value = self.lists_by_id[list_id][task_id]
        value.update(body)
        self.writes += 1
        return dict(value)

    def delete_task(self, list_id, task_id):
        self.lists_by_id[list_id][task_id]["deleted"] = True
        return {}


def test_773_sync_updates_in_place_without_duplicates(env, monkeypatch):
    FakeTasks.lists_by_id, FakeTasks.names, FakeTasks.writes = {}, {}, 0
    monkeypatch.setattr(sync, "TasksClient769", FakeTasks)
    original = sync.projected769
    monkeypatch.setattr(sync, "projected769",
                        lambda db, today, days: original(db, date(2026,11,24), days))
    monkeypatch.setattr(sync, "date", SimpleNamespace(today=lambda: date(2026,11,24)))
    assert sync.sync_once769()["created"] > 0
    with env() as db:
        links = {x.key:x.task_id for x in db.scalars(select(GoogleTasksLink769))}
        med = next(x for x in db.scalars(select(GoogleTasksLink769))
                   if x.kind == "medication" and x.scheduled_on == date(2026,11,24))
        remote = FakeTasks.lists_by_id[med.list_id][med.task_id]
        assert "Detailed Medication" in remote["title"]
        router.update_title773("medication", 1, "Med", db)
    assert sync.sync_once769()["created"] == 0
    with env() as db:
        updated = {x.key:x.task_id for x in db.scalars(select(GoogleTasksLink769))}
        assert updated == links
        med = next(x for x in db.scalars(select(GoogleTasksLink769))
                   if x.kind == "medication" and x.scheduled_on == date(2026,11,24))
        remote = FakeTasks.lists_by_id[med.list_id][med.task_id]
        assert remote["title"] == "07:30 · Med"
        assert "Synthetic Detailed Medication" in remote["notes"]
        assert not remote.get("deleted")
        router.update_title773("medication", 1, "", db)
    assert sync.sync_once769()["created"] == 0
    with env() as db:
        med = next(x for x in db.scalars(select(GoogleTasksLink769))
                   if x.kind == "medication" and x.scheduled_on == date(2026,11,24))
        remote = FakeTasks.lists_by_id[med.list_id][med.task_id]
        assert "Detailed Medication" in remote["title"]
        assert len(FakeTasks.lists_by_id[med.list_id]) == 14


def test_773_completed_google_task_title_not_reopened(env, monkeypatch):
    FakeTasks.lists_by_id, FakeTasks.names, FakeTasks.writes = {}, {}, 0
    monkeypatch.setattr(sync, "TasksClient769", FakeTasks)
    original = sync.projected769
    monkeypatch.setattr(sync, "projected769",
                        lambda db, today, days: original(db, date(2026,11,24), days))
    monkeypatch.setattr(sync, "date", SimpleNamespace(today=lambda: date(2026,11,24)))
    sync.sync_once769()
    with env() as db:
        link = next(x for x in db.scalars(select(GoogleTasksLink769))
                    if x.kind == "protocol" and x.scheduled_on == date(2026,11,24))
        remote = FakeTasks.lists_by_id[link.list_id][link.task_id]
        before = remote["title"]
        remote["status"] = "completed"
        router.update_title773("protocol", 1, "Short protocol", db)
    sync.sync_once769()
    with env() as db:
        link = next(x for x in db.scalars(select(GoogleTasksLink769))
                    if x.kind == "protocol" and x.scheduled_on == date(2026,11,24))
        remote = FakeTasks.lists_by_id[link.list_id][link.task_id]
        assert remote["title"] == before
        assert remote["status"] == "completed"
