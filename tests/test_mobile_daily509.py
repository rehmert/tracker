"""Release 509: mobile Today, quick vital writing and DEV/PROD install identity.

The standard tests/conftest.py creates a separate disposable SQLite database.
"""
from binascii import crc32
import json
from datetime import datetime, timedelta
from pathlib import Path
import struct
import zlib

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.db import SessionLocal
from app.main import app
from app.models import Compound, DoseLog, Vial, VitalReading

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "app/static"


@pytest.fixture(scope="module")
def client():
    with TestClient(app, follow_redirects=False) as c:
        yield c


def test_509_development_and_production_have_distinct_install_identities():
    dev = json.loads((STATIC / "tracker-dev.webmanifest").read_text())
    prod = json.loads((STATIC / "tracker.webmanifest").read_text())
    assert dev["name"] == dev["short_name"] == "Tracker DEV"
    assert prod["name"] == prod["short_name"] == "Tracker"
    assert dev["theme_color"] != prod["theme_color"]
    assert dev["start_url"] == prod["start_url"] == "/mobile"
    assert dev["id"] == prod["id"] == "/"
    assert dev["scope"] == prod["scope"] == "/"
    assert dev["display"] == prod["display"] == "standalone"
    assert {v["url"] for v in dev["shortcuts"]} == {
        "/mobile", "/quick-entry", "/doses", "/vitals",
    }
    for icon in dev["icons"]:
        assert "dev" in icon["src"]
        assert icon["src"].startswith("/static/")
        assert (STATIC / icon["src"].removeprefix("/static/")).is_file()
    for icon in prod["icons"]:
        assert "dev" not in icon["src"]
        assert (STATIC / icon["src"].removeprefix("/static/")).is_file()


def test_509_static_manifests_are_accessible_without_session_cookie(client):
    # Mounted static files are not subject to the application's global
    # authentication dependency. Chrome must be able to fetch installation
    # metadata even when the user has not signed in.
    for path, name in (
        ("/static/tracker-dev.webmanifest", "Tracker DEV"),
        ("/static/tracker.webmanifest", "Tracker"),
    ):
        response = client.get(path)
        assert response.status_code == 200
        assert response.json()["name"] == name
        assert response.json()["start_url"] == "/mobile"
        assert response.headers.get("location") is None


def test_509_no_authenticated_manifest_route_regression():
    html = (ROOT / "app/templates/base.html").read_text()
    router = (ROOT / "app/routers/mobile509.py").read_text()
    assert html.count('rel="manifest"') == 1
    assert "/static/tracker-dev.webmanifest" in html
    assert "/static/tracker.webmanifest" in html
    assert 'href="/tracker.webmanifest"' not in html
    assert '@router.get("/tracker.webmanifest"' not in router


def test_509_dev_android_pngs_are_real_images_not_placeholder_headers():
    for dim in (192, 512):
        raw = (STATIC / f"tracker-icon-dev-{dim}.png").read_bytes()
        assert raw.startswith(b"\x89PNG\r\n\x1a\n")
        assert raw[12:16] == b"IHDR"
        assert struct.unpack(">II", raw[16:24]) == (dim, dim)
        offset = 8
        image = bytearray()
        while offset < len(raw):
            size = struct.unpack(">I", raw[offset:offset + 4])[0]
            kind = raw[offset + 4:offset + 8]
            data = raw[offset + 8:offset + 8 + size]
            checksum = struct.unpack(">I", raw[offset + 8 + size:offset + 12 + size])[0]
            assert crc32(kind + data) == checksum
            if kind == b"IDAT":
                image.extend(data)
            offset += size + 12
            if kind == b"IEND":
                break
        assert offset == len(raw)
        pixels = zlib.decompress(image)
        assert len(pixels) == dim * (1 + dim // 4)
        assert all(pixels[i * (1 + dim // 4)] == 0 for i in range(dim))


def test_509_mobile_today_renders_and_shows_real_quick_form(client):
    resp = client.get("/mobile")
    assert resp.status_code == 200
    assert 'data-mobile-daily509' in resp.text
    assert 'action="/vitals"' in resp.text
    assert 'name="return_to" value="mobile"' in resp.text
    assert 'name="weight"' in resp.text
    assert 'name="systolic"' in resp.text
    assert 'name="diastolic"' in resp.text
    assert 'name="pulse"' in resp.text
    assert 'href="/mobile" aria-current="page"' in resp.text
    assert 'href="/doses#quick-dose-entry"' in resp.text
    assert 'tracker-mobile-daily509.css' in resp.text
    assert 'tracker-mobile-daily509.js' in resp.text


def test_509_inline_vitals_save_and_return_to_mobile(client):
    # The mobile summary sorts by measurement timestamp.
    # Ensure this disposable test reading is the latest.
    with SessionLocal() as db:
        before = db.scalar(select(func.count(VitalReading.id)))
        latest_when = db.scalar(
            select(func.max(VitalReading.measured_at))
        )

    measured_when = datetime.now().replace(microsecond=0)

    if latest_when is not None and latest_when >= measured_when:
        measured_when = latest_when + timedelta(seconds=1)
    response = client.post(
        "/vitals",
        data={
            "return_to": "mobile",
            "measured_at": measured_when.isoformat(timespec="seconds"),
            "weight": "180",
            "weight_unit": "lb",
            "systolic": "124",
            "diastolic": "78",
            "pulse": "65",
            "context": "mobile entry",
        },
    )
    assert response.status_code == 303
    assert response.headers["location"].startswith("/mobile?msg=")
    with SessionLocal() as db:
        assert db.scalar(select(func.count(VitalReading.id))) == before + 1
        row = db.scalar(select(VitalReading).order_by(VitalReading.id.desc()))
        assert row.context == "mobile entry"
        assert row.systolic == 124
        assert row.diastolic == 78
        assert row.pulse_bpm == 65
    page = client.get("/mobile")
    assert page.status_code == 200
    assert "mobile entry" not in page.text  # context is not a public summary
    assert "124/78" in page.text


def test_509_invalid_mobile_vitals_are_rejected_without_new_records(client):
    with SessionLocal() as db:
        before = db.scalar(select(func.count(VitalReading.id)))
    response = client.post(
        "/vitals",
        data={"return_to": "mobile", "systolic": "70", "diastolic": "120"},
    )
    assert response.status_code == 303
    assert response.headers["location"].startswith("/mobile?err=")
    with SessionLocal() as db:
        assert db.scalar(select(func.count(VitalReading.id))) == before


def test_509_mobile_return_to_cannot_redirect_to_arbitrary_url(client):
    response = client.post(
        "/vitals",
        data={"return_to": "https://attacker.invalid/", "weight": "bad"},
    )
    assert response.status_code == 303
    assert response.headers["location"].startswith("/vitals?err=")
    assert "attacker.invalid" not in response.headers["location"]


def test_509_recent_dose_uses_safe_existing_repeat_prefill(client):
    now = datetime.now()
    with SessionLocal() as db:
        compound = Compound(name="Mobile Reuse Test", category="peptide")
        db.add(compound)
        db.flush()
        vial = Vial(
            compound_id=compound.id, label="Mobile vial",
            status="in_use", content_value=100, content_unit="mg",
        )
        db.add(vial)
        db.flush()
        dose = DoseLog(
            vial_id=vial.id, taken_at=now, entered_value=1.5,
            entered_unit="mg", amount_base=1500, kind="dose",
        )
        db.add(dose)
        db.commit()
        dose_id = dose.id

    page = client.get("/mobile")
    assert page.status_code == 200
    assert "Mobile Reuse Test" in page.text
    assert f"/doses?repeat_from={dose_id}#quick-dose-entry" in page.text
    repeated = client.get(f"/doses?repeat_from={dose_id}")
    assert repeated.status_code == 200
    assert "Previous recorded details loaded for review only" in repeated.text


def test_509_mobile_assets_preserve_existing_scope_and_explicit_submission():
    html = (ROOT / "app/templates/mobile_today509.html").read_text()
    js = (STATIC / "js/tracker-mobile-daily509.js").read_text()
    css = (STATIC / "css/tracker-mobile-daily509.css").read_text()
    base = (ROOT / "app/templates/base.html").read_text()
    assert base.count('rel="manifest"') == 1
    assert "/static/tracker-dev.webmanifest" in base
    assert "/static/tracker.webmanifest" in base
    assert 'href="/mobile"' in base
    assert 'tracker-mobile-daily509' in html
    assert 'data-daily-mode="weight"' in html
    assert 'data-daily-mode="bp"' in html
    assert 'data-daily-mode="pulse"' in html
    assert 'data-daily-mode="all"' in html
    assert "Other measurements are filled in" in js
    assert "Saving reading" in js
    assert 'form.dataset.submitting' in js
    assert '.tracker-daily-save' in css
    assert "@media(max-width:760px)" in css
    assert 'action="/doses"' not in html
    assert "serviceWorker" not in js
    for name in ("localStorage", "sessionStorage", "indexedDB"):
        assert name not in js
