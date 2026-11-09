"""Release 528 mobile quick actions and write paths."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.main import app
from app.db import SessionLocal
from app.models import VitalReading

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def client():
    with TestClient(app, follow_redirects=False) as c:
        yield c


def test_528_mobile_sheet_is_accessible(client):
    response = client.get("/mobile")
    assert response.status_code == 200

    markup = response.text

    for marker in (
        'id="tracker-mobile-add528"',
        'aria-controls="tracker-mobile-quick528"',
        'id="tracker-mobile-quick528"',
        'role="dialog"',
        'aria-modal="true"',
        'data-quick528-choice="weight"',
        'data-quick528-choice="bp"',
        'data-quick528-choice="water"',
        'href="/food#food-quick-log"',
        'href="/doses#quick-dose-entry"',
        'href="/labs/new#lab-manual-entry"',
        'data-quick528-another',
        'data-quick528-edit',
        'data-quick528-done',
    ):
        assert marker in markup, marker

    assert markup.count(
        'id="tracker-mobile-quick528"'
    ) == 1

    assert "tracker-mobile-quick528.js?v=528" in markup
    assert "tracker-mobile-quick528.css?v=528" in markup


def test_528_weight_save_returns_edit_link(client):
    with SessionLocal() as db:
        before = db.scalar(
            select(func.count(VitalReading.id))
        )

    response = client.post(
        "/vitals",
        data={
            "weight": "175.5",
            "weight_unit": "lb",
            "measured_at": "2026-11-09T10:30",
            "return_to": "mobile",
        },
        headers={
            "X-Tracker-Mobile-Quick": "528",
            "Accept": "application/json",
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["ok"] is True
    assert data["value"] == "175.5 lb"
    assert data["edit_url"] == (
        f'/vitals/{data["id"]}/edit'
    )

    assert response.headers["cache-control"] == "no-store"

    with SessionLocal() as db:
        after = db.scalar(
            select(func.count(VitalReading.id))
        )

    assert after == before + 1


def test_528_incomplete_bp_cannot_create_record(client):
    with SessionLocal() as db:
        before = db.scalar(
            select(func.count(VitalReading.id))
        )

    response = client.post(
        "/vitals",
        data={
            "systolic": "120",
            "measured_at": "2026-11-09T10:30",
        },
        headers={"X-Tracker-Mobile-Quick": "528"},
    )

    assert response.status_code == 422
    assert response.json()["ok"] is False

    with SessionLocal() as db:
        after = db.scalar(
            select(func.count(VitalReading.id))
        )

    assert after == before


def test_528_water_saves_to_existing_journal(client):
    response = client.post(
        "/food/water",
        data={
            "day": "2026-11-09",
            "ounces": "16.5",
        },
        headers={
            "X-Tracker-Mobile-Quick": "528",
            "Accept": "application/json",
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["ok"] is True
    assert data["value"] == "16.5 fl oz"
    assert data["id"] > 0
    assert data["edit_url"] == (
        "/food?day=2026-11-09#food-water"
    )

    assert response.headers["cache-control"] == "no-store"


def test_528_invalid_water_does_not_save(client):
    response = client.post(
        "/food/water",
        data={
            "day": "2026-11-09",
            "ounces": "0",
        },
        headers={"X-Tracker-Mobile-Quick": "528"},
    )

    assert response.status_code == 422
    assert response.json()["ok"] is False


def test_528_existing_redirects_remain_intact(client):
    response = client.post(
        "/vitals",
        data={
            "weight": "170",
            "weight_unit": "lb",
            "measured_at": "2026-11-09T10:30",
            "return_to": "mobile",
        },
    )

    assert response.status_code == 303
    assert response.headers["location"].startswith(
        "/mobile?msg="
    )

    response = client.post(
        "/food/water",
        data={
            "day": "2026-11-09",
            "ounces": "8",
        },
    )

    assert response.status_code == 303
    assert response.headers["location"] == (
        "/food?day=2026-11-09#food-water"
    )


def test_528_assets_have_no_sensitive_storage():
    javascript = (
        ROOT / "app/static/js/tracker-mobile-quick528.js"
    ).read_text()

    styles = (
        ROOT / "app/static/css/tracker-mobile-quick528.css"
    ).read_text()

    for forbidden in (
        "localStorage",
        "sessionStorage",
        "indexedDB",
        "serviceWorker",
    ):
        assert forbidden not in javascript

    for required in (
        'credentials: "same-origin"',
        "X-Tracker-Mobile-Quick",
        "new FormData(form)",
        "if (busy",
    ):
        assert required in javascript

    assert "focusable" in javascript
    assert "env(safe-area-inset-bottom" in styles
    assert "@media (min-width: 761px)" in styles
