"""Integrated daily workflow: actual route/DB behavior and browser controls."""
from datetime import date, datetime
from pathlib import Path
from uuid import uuid4
import os

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from playwright.sync_api import sync_playwright, expect
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import Base, SessionLocal, engine
from app.main import app
from app.migrations import migrate
from app.models import (ProtocolItem, BlendDose, DoseLog, RegimenItem,
                        RegimenSchedule, RegimenEntry, RegimenTabletSchedule731,
                        RegimenTabletEntry731)
from app.daily_workspace790 import summary790, regimen790
from app.routers.calendar import _month_events
from app.google_protocol_review783 import pending_links783
from tests.test_calendar_quick_dose786 import seed, FormParser
from tests.test_calendar_action_buttons787 import rendered
from tests.test_release783_reconciliation import scenario

ROOT = Path(__file__).resolve().parents[1]


def csrf(client):
    return {"X-Tracker-CSRF": client.cookies["tracker_csrf_v1"]}


def test_790_today_and_dashboard_share_calendar_and_return_after_blend():
    _, items, vials, bid = seed(mixed=True)
    today = date.today()
    with SessionLocal() as db:
        protocol = db.get(ProtocolItem, items[0]).protocol
        protocol.start_date = protocol.end_date = today
        for item in protocol.items:
            item.dose_time = "00:00"
        db.commit()
    with TestClient(app, follow_redirects=False) as client:
        for path, origin in (("/mobile", "today"), ("/", "dashboard")):
            page = client.get(path)
            assert page.status_code == 200
            for item_id in items:
                assert (f"/calendar/log-dose?protocol_item_id={item_id}&amp;scheduled_on={today}"
                        f"&amp;return_to={origin}") in page.text
        page = client.get(f"/calendar/log-dose?protocol_item_id={items[0]}&scheduled_on={today}&return_to=today")
        parser = FormParser()
        parser.feed(page.text)
        assert parser.editable == ["calendar_clock", "site"]
        assert parser.hidden["calendar_origin"] == "today"
        headers = dict(csrf(client), **{"HX-Request": "true"})
        form = dict(parser.hidden, calendar_clock="0000", site="")
        response = client.post("/doses", data=form, headers=headers)
        assert response.headers.get("HX-Redirect") == "/mobile#mobile-schedule-heading"
        assert not client.post("/doses", data=form, headers=headers).headers.get("HX-Redirect")
        overview = client.get("/")
        assert overview.status_code == 200
        for item_id in items:
            assert f"protocol_item_id={item_id}&amp;scheduled_on={today}&amp;return_to=dashboard" not in overview.text
    with SessionLocal() as db:
        assert len(list(db.scalars(select(BlendDose).where(BlendDose.blend_id == bid)))) == 1
        assert not list(db.scalars(select(DoseLog).where(DoseLog.vial_id.in_(vials))))
        canonical = _month_events(today.replace(day=1), db, include_vial_choices=False)[2][today]
        shared = summary790(db, today)["today"]
        assert shared == canonical
        assert all(e["status"] == "recorded" for e in shared if e.get("protocol_item_id") in items)


def test_790_google_pending_is_not_a_due_dose_and_reconcile_returns_to_today(scenario):
    db, key, vid, _, day = scenario
    summary = summary790(db, day)
    assert any(e["status"] == "pending_review" for e in summary["today"])
    assert not any(e["status"] == "due" for e in summary["today"])
    from app.routers import google_tasks769 as google
    local_app = FastAPI()
    local_app.include_router(google.router)
    bind = db.get_bind()
    db.rollback()

    def scoped():
        with Session(bind) as session:
            yield session

    local_app.dependency_overrides[google.get_scoped_db390] = scoped
    path = "/integrations/google-tasks/reconcile"
    fields = {f"choice_{key}": f"vial:{vid}", f"when_{key}": day.isoformat() + "T00:00",
              "confirm": "yes"}
    with TestClient(local_app, follow_redirects=False) as client:
        assert client.post(path, data=dict(fields, return_to="https://invalid.example")).status_code == 400
        response = client.post(path, data=dict(fields, return_to="today"))
        assert response.status_code == 303
        assert response.headers["location"] == "/mobile?review_saved=1#google-protocol-review783"
    db.expire_all()
    assert not pending_links783(db)
    assert len(list(db.scalars(select(DoseLog)))) == 1


def seed_regimen():
    migrate(engine)
    Base.metadata.create_all(engine)
    day = date.today()
    ids = []
    item_ids = []
    with SessionLocal() as db:
        for i in range(3):
            item = RegimenItem(name=f"QA790-{uuid4().hex}", kind="medication" if i == 2 else "supplement", active=True)
            db.add(item)
            db.flush()
            schedule = RegimenSchedule(item_id=item.id, active=True, start_on=day,
                                       cadence="daily", amount="0.5 tablets (10 mg)" if i == 2 else "1 capsule",
                                       at_time="00:00", meal="")
            db.add(schedule)
            db.flush()
            ids.append(schedule.id)
            item_ids.append(item.id)
            if i == 2:
                db.add(RegimenTabletSchedule731(schedule_id=schedule.id, tablet_strength_mg=20,
                                               prescribed_dose_mg=10, tablets_planned=.5))
        db.commit()
        snapshots = regimen790(db, day)["regimen_snapshots"]
    return day, ids, item_ids, snapshots


def test_790_single_and_batch_intake_are_explicit_atomic_and_duplicate_safe():
    day, ids, item_ids, snapshots = seed_regimen()
    with TestClient(app, follow_redirects=False) as client:
        for route in ("/mobile", f"/regimen?day={day}"):
            result = client.get(route)
            assert result.status_code == 200
            assert "Log selected intakes" in result.text
            assert "Adjust time, amount or outcome" in result.text
            assert "schedule_snapshot790" in result.text
        headers = csrf(client)
        single = dict(item_id=item_ids[0], schedule_id=ids[0], logged_at=f"{day}T00:00",
                      outcome="taken", amount="1 capsule", meal="", notes="",
                      scheduled_quick790="yes", scheduled_day790=str(day),
                      schedule_snapshot790=snapshots[ids[0]], return_to="today")
        rejected = client.post("/regimen/entries", data=dict(single, schedule_snapshot790="old"), headers=headers)
        assert "err=" in rejected.headers["location"]
        saved = client.post("/regimen/entries", data=single, headers=headers)
        assert saved.headers["location"].startswith("/mobile?msg=")
        assert saved.headers["location"].endswith("#regimen-today790")
        assert "err=" in client.post("/regimen/entries", data=single, headers=headers).headers["location"]
        batch = {"return_to": "today", "scheduled_day790": str(day), "logged_at": f"{day}T00:00",
                 "schedule_id": [str(ids[1]), str(ids[2])],
                 f"snapshot_{ids[1]}": snapshots[ids[1]], f"snapshot_{ids[2]}": snapshots[ids[2]]}
        bad = dict(batch, **{f"snapshot_{ids[2]}": "old"})
        assert "err=" in client.post("/regimen/entries/batch790", data=bad, headers=headers).headers["location"]
        with SessionLocal() as db:
            assert len(list(db.scalars(select(RegimenEntry).where(RegimenEntry.schedule_id.in_(ids))))) == 1
        assert "msg=" in client.post("/regimen/entries/batch790", data=batch, headers=headers).headers["location"]
        assert "err=" in client.post("/regimen/entries/batch790", data=batch, headers=headers).headers["location"]
    with SessionLocal() as db:
        entries = list(db.scalars(select(RegimenEntry).where(RegimenEntry.schedule_id.in_(ids))))
        assert len(entries) == 3
        tablet = next(e for e in entries if e.schedule_id == ids[2])
        assert tablet.amount == "0.5 tablets (10 mg)"
        assert db.get(RegimenTabletEntry731, tablet.id).administered_dose_mg == 10


@pytest.mark.parametrize("width", [390, 1280])
def test_790_global_quick_add_and_disclosure_navigation(width):
    seed_regimen()
    with TestClient(app) as client:
        today, css = rendered(client, "/mobile")
        regimen, regimen_css = rendered(client, "/regimen")
    js = (ROOT / "app/static/js/tracker-mobile-quick528.js").read_text()
    reveal = (ROOT / "app/static/js/tracker-daily-workspace790.js").read_text()
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True,
            executable_path=os.environ.get("TRACKER_TEST_CHROMIUM_PATH") or None)
        try:
            page = browser.new_page(viewport={"width": width, "height": 900})
            page.route("**/*", lambda route: route.abort())
            page.set_content(today)
            page.add_style_tag(content=css)
            page.add_script_tag(content=js)
            opener = page.locator("#tracker-mobile-add528" if width <= 760 else "#ux-add-toggle")
            opener.click()
            dialog = page.locator("#tracker-mobile-quick528")
            expect(dialog).to_be_visible()
            expect(dialog.locator('[data-quick528-choice="water"]')).to_be_visible()
            dialog.locator("[data-quick528-close]").click()
            expect(dialog).to_be_hidden()
            page.locator(".tracker-quick-actions790 [data-quick790-open='water']").click()
            expect(dialog.locator('[data-quick528-form="water"]')).to_be_visible()
            dialog.locator("[data-quick528-close]").click()
            expect(dialog).to_be_hidden()
            assert page.locator(".tracker-quick-actions790").count() == 1
            expect(page.locator("#regimen-today790 form[data-regimen-quick790]").first.locator("button[type=submit]")).to_be_visible()
            expect(page.locator("#regimen-today790 form[data-regimen-quick790]").first.locator("input[name=logged_at]")).to_be_hidden()
            page.set_content(regimen)
            page.add_style_tag(content=regimen_css)
            page.add_script_tag(content=reveal)
            page.locator('nav[aria-label="Regimen views"] a[href="#reg635-schedules"]').click()
            expect(page.locator("#reg635-schedules > details")).to_have_attribute("open", "")
        finally:
            browser.close()
