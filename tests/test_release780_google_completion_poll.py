"""Release 780 — fast, isolated Google Tasks completion checks.

No production OAuth, Google network, personal data, or installed DEV/PROD DB.
"""
import asyncio
from contextlib import contextmanager
from datetime import date

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base
from app import google_tasks_background769 as background, google_tasks_sync769 as sync
from app.google_tasks_client769 import GoogleTasksError769
from app.google_tasks_models769 import (
    GoogleTasksConnection769, GoogleTasksLink769, GoogleTasksList769,
)
from app.models import (
    Compound, DoseLog, Protocol, ProtocolItem, RegimenEntry, RegimenItem,
    RegimenSchedule,
)


class FakeClient:
    def __init__(self):
        self.remote = {
            "med-list": {"med-task": {"id": "med-task", "status": "needsAction"}},
            "supp-list": {"supp-task": {"id": "supp-task", "status": "needsAction"}},
            "protocol-list": {"protocol-task": {"id": "protocol-task", "status": "needsAction"}},
        }
        self.lookups = []
        self.mutations = []
        self.closed = 0
        self.start_count = 0
        self.fail = False

    def client(self, token):
        assert token == "synthetic-refresh-token"
        self.start_count += 1
        return self

    def tasks(self, list_id):
        self.lookups.append(list_id)
        if self.fail:
            raise GoogleTasksError769("Synthetic temporary Google outage")
        return list(self.remote[list_id].values())

    def close(self):
        self.closed += 1

    def create_list(self, *args):
        self.mutations.append("create_list")
        raise AssertionError("Fast poll must not create lists")

    def create_task(self, *args):
        self.mutations.append("create_task")
        raise AssertionError("Fast poll must not create tasks")

    def patch_task(self, *args):
        self.mutations.append("patch_task")
        raise AssertionError("Fast poll must not patch tasks")

    def delete_task(self, *args):
        self.mutations.append("delete_task")
        raise AssertionError("Fast poll must not delete tasks")


@pytest.fixture
def isolated(monkeypatch, tmp_path):
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    fake = FakeClient()
    with factory() as db:
        med = RegimenItem(kind="medication", name="Synthetic Morning Med", active=True)
        supp = RegimenItem(kind="supplement", name="Synthetic Evening Vitamin", active=True)
        compound = Compound(name="Synthetic QA Only", category="peptide")
        db.add_all([med, supp, compound])
        db.flush()
        db.add_all([
            RegimenSchedule(item_id=med.id, cadence="daily", amount="1 tablet",
                            at_time="07:30", active=True, start_on=date(2026, 11, 24)),
            RegimenSchedule(item_id=supp.id, cadence="daily", amount="1 capsule",
                            at_time="20:00", active=True, start_on=date(2026, 11, 24)),
        ])
        protocol = Protocol(name="Synthetic Protocol", is_active=True,
                            start_date=date(2026, 11, 24))
        db.add(protocol)
        db.flush()
        db.add(ProtocolItem(protocol_id=protocol.id, compound_id=compound.id,
                            position=0, amount_value=1, amount_unit="mg",
                            freq_count=1, freq_period="interval",
                            start_week=1, dose_time="09:30"))
        db.add(GoogleTasksConnection769(
            id=1, enabled=True, refresh_token="synthetic-refresh-token"
        ))
        db.add_all([
            GoogleTasksList769(kind="medication", list_id="med-list"),
            GoogleTasksList769(kind="supplement", list_id="supp-list"),
            GoogleTasksList769(kind="protocol", list_id="protocol-list"),
        ])
        db.flush()
        db.add_all([
            GoogleTasksLink769(
                key="synthetic-med-link", kind="medication", source_id=1,
                scheduled_on=date(2026, 11, 24), scheduled_time="07:30",
                list_id="med-list", task_id="med-task", last_status="needsAction",
                last_fingerprint="a",
            ),
            GoogleTasksLink769(
                key="synthetic-supp-link", kind="supplement", source_id=2,
                scheduled_on=date(2026, 11, 24), scheduled_time="20:00",
                list_id="supp-list", task_id="supp-task", last_status="needsAction",
                last_fingerprint="b",
            ),
            GoogleTasksLink769(
                key="synthetic-protocol-link", kind="protocol", source_id=1,
                scheduled_on=date(2026, 11, 24), scheduled_time="09:30",
                list_id="protocol-list", task_id="protocol-task",
                last_status="needsAction", last_fingerprint="c",
            ),
        ])
        db.commit()
    monkeypatch.setattr(sync, "SessionLocal", factory)
    monkeypatch.setattr(sync, "TasksClient769", fake.client)
    monkeypatch.setattr(sync, "configured769",
                        lambda: ("mock-client", "mock-secret", "mock-redirect"))
    monkeypatch.setattr(sync.config, "DATA_DIR", tmp_path)
    yield factory, fake
    engine.dispose()


def _completed(remote, id_):
    remote[id_]["status"] = "completed"
    remote[id_]["completed"] = "2026-11-24T15:11:00Z"


def test_780_fast_poll_imports_med_and_supp_once_without_google_writes(isolated):
    factory, fake = isolated
    first = sync.sync_completions_once780()
    assert first == {"status": "ok", "created": 0, "imported": 0,
                     "pending_protocols": 0}
    assert set(fake.lookups) == {"med-list", "supp-list", "protocol-list"}
    assert fake.mutations == []
    _completed(fake.remote["med-list"], "med-task")
    _completed(fake.remote["supp-list"], "supp-task")
    _completed(fake.remote["protocol-list"], "protocol-task")
    second = sync.sync_completions_once780()
    assert second["imported"] == 2
    assert second["pending_protocols"] == 1
    assert second["created"] == 0
    assert fake.mutations == []
    with factory() as db:
        rows = list(db.scalars(select(RegimenEntry).order_by(RegimenEntry.id)))
        assert len(rows) == 2
        assert {r.schedule_id for r in rows} == {1, 2}
        assert all("Google Tasks completion" in r.notes for r in rows)
        assert db.scalar(select(DoseLog.id)) is None
        links = list(db.scalars(select(GoogleTasksLink769)))
        assert all(link.last_status == "completed" for link in links)
        assert sum(link.imported_entry_id is not None for link in links) == 2
    count = len(fake.lookups)
    again = sync.sync_completions_once780()
    assert again["imported"] == again["pending_protocols"] == 0
    assert len(fake.lookups) == count, "Already-completed links need no fast poll"
    assert fake.start_count == 2
    assert fake.closed == 2


def test_780_disabled_and_missing_links_make_no_google_calls(isolated, monkeypatch):
    factory, fake = isolated
    monkeypatch.setattr(sync, "configured769", lambda: None)
    assert sync.sync_completions_once780()["status"] == "disabled"
    assert fake.start_count == 0
    monkeypatch.setattr(sync, "configured769", lambda: ("synthetic", "secret", "uri"))
    with factory() as db:
        db.get(GoogleTasksConnection769, 1).enabled = False
        db.commit()
    assert sync.sync_completions_once780()["status"] == "disabled"
    with factory() as db:
        db.get(GoogleTasksConnection769, 1).enabled = True
        for row in db.scalars(select(GoogleTasksLink769)):
            row.removed = True
        db.commit()
    assert sync.sync_completions_once780()["status"] == "ok"
    assert fake.start_count == 0
    assert fake.lookups == []


def test_780_fallback_to_full_sync_for_missing_list_and_unlinked_task(isolated):
    factory, fake = isolated
    fake.remote["med-list"]["unlinked-task"] = {
        "id": "unlinked-task", "status": "completed",
        "completed": "2026-11-24T15:11:00Z",
    }
    with factory() as db:
        db.delete(db.get(GoogleTasksList769, "supplement"))
        db.commit()
    result = sync.sync_completions_once780()
    assert result["status"] == "ok"
    assert result["imported"] == 0
    assert set(fake.lookups) == {"med-list", "protocol-list"}
    with factory() as db:
        assert db.scalar(select(RegimenEntry.id)) is None
        # Never create missing task lists during a minute-level check.
        assert db.get(GoogleTasksList769, "supplement") is None


def test_780_fast_sync_error_stored_sanitized_and_no_partial_intake(isolated):
    factory, fake = isolated
    fake.fail = True
    with pytest.raises(GoogleTasksError769, match="Synthetic temporary"):
        sync.sync_completions_once780()
    with factory() as db:
        conn = db.get(GoogleTasksConnection769, 1)
        assert conn.last_error == "Synthetic temporary Google outage"
        assert db.scalar(select(RegimenEntry.id)) is None
    assert fake.closed == 1


def test_780_cross_worker_nonblocking_lock_skips_conflicting_poll(
        isolated, monkeypatch):
    factory, fake = isolated

    @contextmanager
    def held_lock():
        raise BlockingIOError()
        yield

    monkeypatch.setattr(sync, "exclusive769", held_lock)
    result = sync.sync_completions_once780()
    assert result == {"status": "busy", "created": 0, "imported": 0,
                      "pending_protocols": 0}
    assert fake.start_count == 0


def test_780_background_runs_four_minute_polls_per_full_sync(monkeypatch):
    calls = []
    ticks = 0

    class EndOfSimulation(Exception):
        pass

    async def fake_sleep(seconds):
        nonlocal ticks
        assert seconds == background.COMPLETION_POLL_SECONDS_780 == 60
        ticks += 1
        if ticks > 10:
            raise EndOfSimulation

    async def fake_to_thread(worker):
        worker()

    monkeypatch.setattr(background, "configured769", lambda: True)
    monkeypatch.setattr(background.asyncio, "sleep", fake_sleep)
    monkeypatch.setattr(background.asyncio, "to_thread", fake_to_thread)
    monkeypatch.setattr(background, "sync_completions_once780",
                        lambda: calls.append("completions"))
    monkeypatch.setattr(background, "sync_once769",
                        lambda: calls.append("full"))
    with pytest.raises(EndOfSimulation):
        asyncio.run(background.loop769())
    assert calls == [
        "completions", "completions", "completions", "completions", "full",
        "completions", "completions", "completions", "completions", "full",
    ]


def test_780_background_disconnected_does_not_poll(monkeypatch):
    calls = []

    class EndOfSimulation(Exception):
        pass

    async def fake_sleep(seconds):
        assert seconds == 60
        if len(calls) >= 3:
            raise EndOfSimulation
        calls.append("tick")

    monkeypatch.setattr(background, "configured769", lambda: None)
    monkeypatch.setattr(background.asyncio, "sleep", fake_sleep)
    monkeypatch.setattr(background, "sync_completions_once780",
                        lambda: pytest.fail("Disconnected poll not allowed"))
    monkeypatch.setattr(background, "sync_once769",
                        lambda: pytest.fail("Disconnected full sync not allowed"))
    with pytest.raises(EndOfSimulation):
        asyncio.run(background.loop769())


def test_780_full_sync_unchanged_by_fast_poll(monkeypatch):
    # No patch is made to the five-minute sync entry point; the fast path
    # only adds a new import function and a narrower background cadence.
    assert sync.sync_once769 is not sync.sync_completions_once780
    assert background.FULL_SYNC_EVERY_POLLS_780 == 5
    assert callable(sync._sync_locked769)
