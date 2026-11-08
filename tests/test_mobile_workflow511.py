"""Release 511: mobile dose selection, safe reuse and Today navigation.

Tests use the fully isolated SQLite DB configured by tests/conftest.py.
"""
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.db import SessionLocal
from app.main import app
from app.models import DoseLog, Vial
from app import services
from app.mobile_shortcuts511 import recent_preparations
from tests.test_stage17_dose_blend_integrity import seed_vials

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture()
def client():
    with TestClient(app, follow_redirects=False) as tc:
        yield tc


def make_record(client, vial_id, amount="2", kind="dose"):
    response = client.post("/doses", data={
        "vial_id": str(vial_id),
        "taken_at": "2026-11-08T08:30",
        "amount": amount,
        "unit": "mg",
        "kind": kind,
        "submission_token": str(uuid4()),
    })
    assert response.status_code == 200, response.text[:250]
    assert 'HX-Trigger-After-Settle' in response.headers


def test_511_recent_preparations_only_returns_valid_available_doses(client):
    vials = seed_vials("Recent511-" + uuid4().hex, 3)
    make_record(client, vials[0], "2")
    make_record(client, vials[1], "9")
    make_record(client, vials[2], "1", kind="waste")
    with SessionLocal() as db:
        items = list(db.scalars(select(Vial).where(Vial.id.in_(vials))))
        views = services.vial_views(db, items)
        result = recent_preparations(db, items, views)
        assert [item["vial_id"] for item in result] == [vials[0]]
        assert result[0]["amount"] == 2
        assert result[0]["unit"] == "mg"
        assert len(result) == 1


def test_511_recent_preparations_deduplicates_compounds(client):
    vial_id = seed_vials("Duplicate511-" + uuid4().hex, 1)[0]
    make_record(client, vial_id, "2")
    make_record(client, vial_id, "1")
    with SessionLocal() as db:
        vials = [db.get(Vial, vial_id)]
        result = recent_preparations(db, vials, services.vial_views(db, vials))
        assert len(result) == 1
        assert result[0]["amount"] == 1


def test_511_recent_preparations_skips_closed_vials(client):
    vial_id = seed_vials("Unavailable511-" + uuid4().hex, 1)[0]
    make_record(client, vial_id, "2")
    with SessionLocal() as db:
        vial = db.get(Vial, vial_id)
        vial.status = "discarded"
        db.commit()
        result = recent_preparations(db, [vial], {})
        assert result == []


def test_511_dose_page_has_search_and_safe_recent_choices(client):
    vial_id = seed_vials("Form511-" + uuid4().hex, 1)[0]
    make_record(client, vial_id, "2")
    with SessionLocal() as db:
        dose_id = db.scalar(
            select(DoseLog.id).where(DoseLog.vial_id == vial_id)
        )
    response = client.get("/doses")
    assert response.status_code == 200
    html = response.text
    assert 'data-vial-finder511' in html
    assert 'data-vial-search511' in html
    assert 'data-vial-matches511' in html
    assert f'data-vial-choice511="{vial_id}"' in html
    assert f'/doses?repeat_from={dose_id}#quick-dose-entry' in html
    assert 'hx-post="/doses"' in html
    assert 'name="submission_token"' in html
    assert 'name="vial_id" required' in html
    assert 'tracker-vial-finder511.js?v=511' in html
    assert 'tracker-mobile-accelerators511.css?v=511' in html


def test_511_calendar_handoff_cannot_be_contaminated_by_recent_vials(client):
    vial_id = seed_vials("Planned511-" + uuid4().hex, 1)[0]
    make_record(client, vial_id, "2")
    with SessionLocal() as db:
        compound_id = db.get(Vial, vial_id).compound_id
    response = client.get(
        f"/doses?compound_id={compound_id}"
        "&planned_date=2026-11-08&planned_amount=1&planned_unit=mg"
    )
    assert response.status_code == 200
    assert "Recently used compounds" not in response.text
    assert 'data-vial-finder511' in response.text
    assert 'name="planned_compound_id"' in response.text


def test_511_today_includes_read_only_repeat_cards_and_jumps(client):
    vial_id = seed_vials("Today511-" + uuid4().hex, 1)[0]
    make_record(client, vial_id, "2")
    with SessionLocal() as db:
        dose_id = db.scalar(
            select(DoseLog.id).where(DoseLog.vial_id == vial_id)
        )
        before = db.scalar(select(func.count()).select_from(DoseLog))
    response = client.get("/mobile")
    assert response.status_code == 200
    html = response.text
    assert 'id="mobile-reuse-heading511"' in html
    assert f'/doses?repeat_from={dose_id}#quick-dose-entry' in html
    assert 'href="#mobile-schedule-heading"' in html
    assert 'href="#mobile-upcoming-heading"' in html
    assert 'data-daily-now511' in html
    assert 'tracker-mobile-daily509.js?v=511' in html
    assert 'tracker-mobile-daily509.css?v=511' in html
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(DoseLog)) == before
    review = client.get(f"/doses?repeat_from={dose_id}")
    assert "Previous recorded details loaded for review only" in review.text


def test_511_client_search_only_updates_existing_vial_selector():
    js = (ROOT / "app/static/js/tracker-vial-finder511.js").read_text()
    assert 'select[name="vial_id"]' in js
    assert 'select.value = id' in js
    assert 'dispatchEvent(new Event("change", { bubbles: true }))' in js
    assert 'if (event.key === "Enter") {' in js
    assert 'if (shown.length) choose(shown[0].id);' in js
    assert 'event.preventDefault();' in js
    assert 'button.type = "button"' in js
    assert 'document.createElement("button")' in js
    assert 'button.textContent = item.label' in js
    for forbidden in ("form.submit(", "fetch(", "localStorage", "sessionStorage", "indexedDB"):
        assert forbidden not in js


def test_511_today_current_time_is_local_and_requires_explicit_save():
    js = (ROOT / "app/static/js/tracker-mobile-daily509.js").read_text()
    html = (ROOT / "app/templates/mobile_today509.html").read_text()
    assert 'data-daily-now511' in html
    assert 'new Date()' in js
    assert 'now.getHours()' in js
    assert 'timeInput.value = currentLocalTime()' in js
    assert 'Recording time updated' in js
    assert 'form.submit()' not in js
    assert '<details class="tracker-daily-more511">' in html
    assert 'summary.upcoming[8:]' in html


def test_511_empty_dose_history_still_renders_and_accepts_search(client):
    vial_id = seed_vials("Fresh511-" + uuid4().hex, 1)[0]
    # No dose is needed for this vial's native select option to be searchable.
    response = client.get("/doses")
    assert response.status_code == 200
    assert f'value="{vial_id}"' in response.text
    assert 'data-vial-finder511' in response.text
    assert 'name="submission_token"' in response.text
