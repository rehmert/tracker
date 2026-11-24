"""Release 778: preserve regimen edit context across full-page POST redirects.

Synthetic SQLite only. Test native GET/POST navigation (no JavaScript, no
credentials, no medical data). All 303 redirects retain the existing PRG flow.
"""
from datetime import date
from pathlib import Path
import re
from urllib.parse import parse_qs, urlsplit

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base, get_db
from app.models import RegimenItem, RegimenSchedule
from app.routers import regimen635

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def env():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False},
                           poolclass=StaticPool)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    app = FastAPI()
    app.include_router(regimen635.router)

    def isolated():
        with factory() as db:
            yield db

    app.dependency_overrides[get_db] = isolated
    with TestClient(app, follow_redirects=False) as client:
        yield client, factory
    engine.dispose()


def item(client, kind="medication"):
    return client.post("/regimen/items", data={
        "kind": kind, "name": "Synthetic Regimen " + kind,
        "strength": "10 mg", "form": "Tablet",
    })


def schedule(client):
    return client.post("/regimen/schedules", data={
        "item_id": "1", "cadence": "daily",
        "amount": "1 tablet", "start_on": "2026-11-24", "at_time": "07:30",
    })


def assert_focus(response, name):
    assert response.status_code == 303, response.text
    url = urlsplit(response.headers["location"])
    assert url.path == "/regimen"
    assert parse_qs(url.query)["focus"] == [name]
    assert url.fragment == "reg635-" + name
    assert "msg" in parse_qs(url.query) or "err" in parse_qs(url.query)
    return response.headers["location"]


def card(html, entity, source_id):
    match = re.search(
        rf'<article class="reg635-card" id="reg635-{entity}-{source_id}">'
        rf'(.*?)</article>',
        html, re.S,
    )
    assert match, f"{entity} card missing"
    return match.group(1)


@pytest.mark.parametrize("kind", ["medication", "supplement"])
def test_778_schedule_save_returns_to_open_editor_and_preserves_record(env, kind):
    client, factory = env
    assert_focus(item(client, kind), "item-1")
    assert_focus(schedule(client), "schedule-1")
    unchanged = client.get("/regimen")
    assert unchanged.status_code == 200
    assert re.search(r'<details class="reg733-edit-panel"\s*>'
                     r'<summary[^>]*>Edit schedule', card(unchanged.text, "schedule", 1))
    edit = client.post("/regimen/schedules/1/edit", data={
        "cadence": "daily", "amount": "2 tablets",
        "start_on": "2026-11-24", "at_time": "20:30", "active": "yes",
    })
    url = assert_focus(edit, "schedule-1")
    page = client.get(url)
    assert page.status_code == 200
    target = card(page.text, "schedule", 1)
    assert re.search(r'<details class="reg733-edit-panel"\s+open>'
                     r'<summary[^>]*>Edit schedule', target)
    assert 'value="20:30"' in target
    assert 'value="2 tablets"' in target
    with factory() as db:
        saved = db.get(RegimenSchedule, 1)
        assert saved.amount == "2 tablets"
        assert saved.at_time == "20:30"
        assert saved.item.kind == kind


def test_778_invalid_schedule_submit_returns_to_open_editor_without_mutation(env):
    client, factory = env
    item(client)
    schedule(client)
    bad = client.post("/regimen/schedules/1/edit", data={
        "cadence": "invalid", "amount": "5 tablets",
        "start_on": "2026-11-24", "active": "yes",
    })
    url = assert_focus(bad, "schedule-1")
    assert "err" in parse_qs(urlsplit(url).query)
    page = client.get(url)
    assert 'class="reg733-edit-panel" open' in card(page.text, "schedule", 1)
    with factory() as db:
        assert db.get(RegimenSchedule, 1).amount == "1 tablet"


def test_778_create_schedule_error_opens_new_schedule_form(env):
    client, _ = env
    item(client)
    bad = client.post("/regimen/schedules", data={
        "item_id": "1", "cadence": "weekly", "weekdays": "9",
        "start_on": "2026-11-24", "amount": "1 tablet",
    })
    url = assert_focus(bad, "add-schedule")
    page = client.get(url)
    assert page.status_code == 200
    assert '<details id="reg635-add-schedule" open>' in page.text


def test_778_edit_item_returns_to_matching_open_catalog_editor(env):
    client, factory = env
    item(client)
    updated = client.post("/regimen/items/1/edit", data={
        "kind": "medication", "name": "Synthetic New Name", "active": "yes",
        "strength": "20 mg",
    })
    url = assert_focus(updated, "item-1")
    html = client.get(url).text
    target = card(html, "item", 1)
    assert 'class="reg733-edit-panel" open' in target
    assert 'value="Synthetic New Name"' in target
    with factory() as db:
        assert db.get(RegimenItem, 1).name == "Synthetic New Name"


def test_778_catalog_create_validation_returns_to_open_add_form(env):
    client, _ = env
    bad = client.post("/regimen/items", data={
        "kind": "medication", "name": "",
    })
    url = assert_focus(bad, "add-item")
    assert '<details id="reg635-add-item" open>' in client.get(url).text


def test_778_stop_and_delete_stay_in_schedule_section(env):
    client, factory = env
    item(client)
    schedule(client)
    stopped = client.post("/regimen/schedules/1/stop")
    assert_focus(stopped, "schedule-1")
    deleted = client.post("/regimen/schedules/1/delete",
                          data={"confirm_delete": "delete"})
    url = assert_focus(deleted, "schedules")
    page = client.get(url)
    assert page.status_code == 200
    assert '<section class="card" id="reg635-schedules">' in page.text
    with factory() as db:
        assert db.scalar(select(RegimenSchedule.id)) is None


def test_778_flash_redirect_retains_day_and_puts_fragment_after_message():
    response = regimen635._redirect(day=date(2026,11,24),
                                   msg="Schedule updated.",
                                   focus="schedule-42")
    url = urlsplit(response.headers["location"])
    assert url.path == "/regimen"
    assert parse_qs(url.query) == {
        "day": ["2026-11-24"],
        "focus": ["schedule-42"], "msg": ["Schedule updated."],
    }
    assert url.fragment == "reg635-schedule-42"


@pytest.mark.parametrize("unsafe", [
    "#reg635-schedule-1", "https://elsewhere.test/",
    "schedule-1?foo=bar", "schedule--1", "../regimen", "item-0",
])
def test_778_redirect_destination_is_allowlisted(unsafe):
    with pytest.raises(ValueError, match="Invalid regimen return destination"):
        regimen635._redirect(msg="x", focus=unsafe)


def test_778_template_is_mobile_compatible_and_existing_routes_stable():
    template = (ROOT / "app/templates/regimen635.html").read_text(encoding="utf-8")
    assert 'id="reg635-schedule-{{ schedule.id }}"' in template
    assert 'id="reg635-item-{{ item.id }}"' in template
    assert "return_focus == 'schedule-' ~ schedule.id" in template
    assert "return_focus == 'item-' ~ item.id" in template
    assert "scroll-margin-top:5rem" in template
    assert 'action="/regimen/schedules/{{ schedule.id }}/edit"' in template
    assert 'action="/regimen/items/{{ item.id }}/edit"' in template
    assert "reg635-grid" in template
