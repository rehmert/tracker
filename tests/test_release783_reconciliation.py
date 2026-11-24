from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
from jinja2 import Environment
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.db import Base
from app.models import Compound, Protocol, ProtocolItem, Vial, DoseLog
from app.google_tasks_models769 import GoogleTasksLink769
from app.google_tasks_projection769 import projected769
from app.google_tasks_sync769 import _fingerprint
from app.google_protocol_review783 import (
    auto_reconcile783, review_rows783, reconcile_choice783, pending_links783,
)
from app.inventory_lock import require_inventory_write
from app.routers.calendar import _month_events, calendar_status_counts
from app.services import vial_views

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def scenario(tmp_path):
    engine = create_engine("sqlite:///" + str(tmp_path / "synthetic.db"))
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        now = datetime.now(ZoneInfo("America/New_York"))
        day = now.date()
        compound = Compound(name="Synthetic compound", category="peptide")
        protocol = Protocol(name="Synthetic plan", is_active=True, start_date=day)
        db.add_all([compound, protocol])
        db.flush()
        item = ProtocolItem(protocol_id=protocol.id, compound_id=compound.id,
                            amount_value=1, amount_unit="mg", freq_count=1,
                            freq_period="day", dose_time="00:00")
        vial = Vial(compound_id=compound.id, label="Synthetic source",
                    status="in_use", content_value=10, content_unit="mg",
                    volume_ml=2, form="liquid")
        db.add_all([item, vial])
        db.flush()
        occ = next(o for o in projected769(db, day, 1).values() if o.kind == "protocol")
        body = occ.task_body()
        link = GoogleTasksLink769(key=occ.key, kind="protocol", source_id=item.id,
                                 scheduled_on=day, scheduled_time="00:00",
                                 list_id="synthetic-list", task_id="synthetic-task",
                                 last_status="completed", last_fingerprint=_fingerprint(body))
        db.add(link)
        key, vid = link.key, vial.id
        db.commit()
        remote = dict(body, status="completed", completed=now.isoformat())
        yield db, key, vid, remote, day
    engine.dispose()


def test_783_auto_records_once_and_reduces_inventory(scenario):
    db, key, vid, remote, day = scenario
    assert auto_reconcile783(db, key, remote, _fingerprint)
    assert not auto_reconcile783(db, key, remote, _fingerprint)
    records = list(db.scalars(select(DoseLog)))
    assert len(records) == 1 and records[0].amount_base == 1000
    assert db.get(GoogleTasksLink769, key).imported_entry_id == records[0].id
    assert vial_views(db, [db.get(Vial, vid)])[vid].remaining_base == 9000
    assert not pending_links783(db)
    _, _, events, _ = _month_events(day.replace(day=1), db)
    assert events[day][0]["status"] == "recorded"


def test_783_ambiguous_inventory_stays_visible_and_can_be_confirmed(scenario):
    db, key, vid, remote, day = scenario
    vial = db.get(Vial, vid)
    db.add(Vial(compound_id=vial.compound_id, label="Other synthetic source",
                status="in_use", content_value=10, content_unit="mg",
                volume_ml=2, form="liquid"))
    db.commit()
    assert not auto_reconcile783(db, key, remote, _fingerprint)
    assert not list(db.scalars(select(DoseLog)))
    assert len(review_rows783(db)) == 1
    _, _, events, _ = _month_events(day.replace(day=1), db)
    assert events[day][0]["status"] == "pending_review"
    assert calendar_status_counts([{"in_month": True, "events": events[day]}])["pending_review"] == 1
    db.rollback()
    require_inventory_write(db)
    reconcile_choice783(db, key, f"vial:{vid}", day.isoformat() + "T00:00")
    db.commit()
    assert not pending_links783(db)
    assert len(list(db.scalars(select(DoseLog)))) == 1


def test_783_changed_remote_payload_cannot_auto_record(scenario):
    db, key, vid, remote, day = scenario
    remote["notes"] += " edited"
    assert not auto_reconcile783(db, key, remote, _fingerprint)
    assert len(pending_links783(db)) == 1
    assert not list(db.scalars(select(DoseLog)))


def test_783_existing_dose_is_matched_without_second_withdrawal(scenario):
    db, key, vid, remote, day = scenario
    dose = DoseLog(vial_id=vid, taken_at=datetime.combine(day, datetime.min.time()),
                   entered_value=1, entered_unit="mg", amount_base=1000, kind="dose")
    db.add(dose)
    db.flush()
    did = dose.id
    db.commit()
    assert not auto_reconcile783(db, key, remote, _fingerprint)
    assert review_rows783(db)[0]["choices"][0][0] == f"dose:{did}"
    db.rollback()
    require_inventory_write(db)
    reconcile_choice783(db, key, f"dose:{did}", "")
    db.commit()
    assert not pending_links783(db)
    assert len(list(db.scalars(select(DoseLog)))) == 1


def test_783_vitals_four_word_preview_and_full_note_contract():
    template = (ROOT / "app/templates/vitals.html").read_text()
    Environment().parse(template)
    assert "words[:4]|join(' ')" in template
    assert "words|length > 4" in template
    assert 'data-vitals-full-notes="{{ r.notes or' in template
    assert 'href="#vitals-readings"' in template
    assert 'class="vitals-actions783"' in template
    js = (ROOT / "app/static/js/tracker-vitals-tools.js").read_text()
    assert js.count("cell.dataset.vitalsFullNotes ?? cell.textContent") == 2
    css = (ROOT / "app/static/css/tracker-vitals-tools.css").read_text()
    assert "max-width: 12rem" in css
    assert "white-space: pre-wrap" in css
