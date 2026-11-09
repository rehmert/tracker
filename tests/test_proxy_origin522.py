"""Release 522: regression for LAN Vitals writes through a TLS Host-rewriting proxy.

Every request uses the real Tracker middleware and a disposable pytest SQLite
database. No network request is sent to installed DEV/PROD services.
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from starlette.datastructures import Headers

from app import config
from app.csrf_runtime import COOKIE_NAME, HEADER_NAME
from app.db import SessionLocal
from app.main import app
from app.models import VitalReading
from app.proxy_origin522 import allow_signed_proxy_write522


@pytest.fixture
def proxy_client522(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "AUTH_USER", "")
    monkeypatch.setattr(config, "AUTH_PASS", "")
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    monkeypatch.setenv("TRACKER_ORIGIN_GUARD", "1")
    monkeypatch.setenv("TRACKER_CSRF_ENFORCE", "0")
    with TestClient(app, base_url="http://tracker-internal:8000") as client:
        home = client.get("/vitals")
        assert home.status_code == 200
        token = client.cookies.get(COOKIE_NAME)
        assert token
        yield client, token


def _count522(label):
    with SessionLocal() as db:
        return db.scalar(
            select(func.count()).select_from(VitalReading)
            .where(VitalReading.context == label)
        )


def _form522(label, token=None):
    fields = {
        "measured_at": "2026-11-08T20:30",
        "weight": "180",
        "weight_unit": "lb",
        "systolic": "120",
        "diastolic": "76",
        "pulse": "68",
        "context": label,
    }
    if token is not None:
        fields["csrf_token"] = token
    return fields


@pytest.mark.parametrize("origin", (
    "https://tracker.example",
    "https://tracker.example:8443",
    "http://tracker.example:8080",
    "null",
))
def test_522_proxy_native_vitals_create_reaches_route(proxy_client522, origin):
    client, token = proxy_client522
    label = "QA signed Vitals proxy 522"
    before = _count522(label)
    response = client.post(
        "/vitals",
        data=_form522(label, token),
        headers={
            "Origin": origin,
            "Sec-Fetch-Site": "same-origin",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text[:200]
    assert response.headers["location"].startswith("/vitals")
    assert response.headers["x-tracker-csrf-report"] == "valid"
    assert _count522(label) == before + 1


@pytest.mark.parametrize("fetch_site,origin,token_status", (
    ("same-origin", "https://tracker.example", "missing"),
    ("same-origin", "https://tracker.example", "forged"),
    ("same-origin", "null", "missing"),
    ("same-origin", "null", "forged"),
    ("same-site", "https://tracker.example", "valid"),
    ("cross-site", "https://tracker.example", "valid"),
    ("", "https://tracker.example", "valid"),
    ("none", "null", "valid"),
    ("same-origin", "https://tracker.example/path", "valid"),
    ("same-origin", "https://user@tracker.example", "valid"),
    ("same-origin", "NULL", "valid"),
    ("same-origin", "http://bad host", "valid"),
))
def test_522_proxy_unsafe_or_unsigned_vitals_never_mutates(
    proxy_client522, fetch_site, origin, token_status,
):
    client, token = proxy_client522
    label = "QA denied Vitals proxy 522"
    before = _count522(label)
    submitted = (
        token if token_status == "valid"
        else ("forged-token" if token_status == "forged" else None)
    )
    headers = {"Origin": origin}
    if fetch_site:
        headers["Sec-Fetch-Site"] = fetch_site
    response = client.post(
        "/vitals",
        data=_form522(label, submitted),
        headers=headers,
        follow_redirects=False,
    )
    assert response.status_code == 403
    assert response.text == "Cross-origin write request denied."
    assert _count522(label) == before


def test_522_proxy_vitals_edit_and_htmx_delete_use_signed_proof(proxy_client522):
    client, token = proxy_client522
    label = "QA proxy update 522"
    created = client.post(
        "/vitals", data=_form522(label, token),
        headers={
            "Origin": "https://tracker.example",
            "Sec-Fetch-Site": "same-origin",
        },
        follow_redirects=False,
    )
    assert created.status_code == 303
    with SessionLocal() as db:
        record = db.scalar(select(VitalReading).where(VitalReading.context == label))
        assert record is not None
        rid = record.id

    edit = client.post(
        f"/vitals/{rid}/edit",
        data=_form522("QA edited proxy 522", token),
        headers={
            "Origin": "https://tracker.example",
            "Sec-Fetch-Site": "same-origin",
        },
        follow_redirects=False,
    )
    assert edit.status_code == 303
    assert edit.headers["x-tracker-csrf-report"] == "valid"
    with SessionLocal() as db:
        assert db.get(VitalReading, rid).context == "QA edited proxy 522"

    denied = client.request(
        "DELETE", f"/vitals/{rid}",
        headers={
            "Origin": "https://tracker.example",
            "Sec-Fetch-Site": "same-origin",
            HEADER_NAME: "forged-token",
        },
    )
    assert denied.status_code == 403
    with SessionLocal() as db:
        assert db.get(VitalReading, rid) is not None

    deleted = client.request(
        "DELETE", f"/vitals/{rid}",
        headers={
            "Origin": "https://tracker.example",
            "Sec-Fetch-Site": "same-origin",
            HEADER_NAME: token,
        },
    )
    assert deleted.status_code == 200
    assert deleted.headers.get("hx-refresh") == "true"
    assert deleted.headers["x-tracker-csrf-report"] == "valid"
    with SessionLocal() as db:
        assert db.get(VitalReading, rid) is None


@pytest.mark.parametrize("origin", ("https://tracker.example", "null"))
def test_522_proxy_native_multipart_labs_upload_verified_at_route(
    proxy_client522, origin,
):
    """A signed HTML multipart field must pass proxy guard in report-only mode.

    The invalid CSV deliberately reaches normal endpoint validation and does
    not create any lab report. Middleware must not preconsume the upload body.
    """
    client, token = proxy_client522
    headers = {"Origin": origin, "Sec-Fetch-Site": "same-origin"}
    payload = {
        "csrf_token": token,
        "drawn_on": "2026-11-08",
        "lab_name": "QA multipart proxy 522",
    }
    accepted = client.post(
        "/labs/import-csv",
        headers=headers,
        data=payload,
        files={"csv_file": ("bad.csv", b"not,a,valid,csv\\n", "text/csv")},
        follow_redirects=False,
    )
    assert accepted.status_code != 403
    assert accepted.headers["x-tracker-csrf-report"] == "valid"

    no_token = client.post(
        "/labs/import-csv",
        headers=headers,
        data={"drawn_on": "2026-11-08"},
        files={"csv_file": ("bad.csv", b"bad\\n", "text/csv")},
        follow_redirects=False,
    )
    assert no_token.status_code == 403
    assert "CSRF token required" in no_token.text

    forged = client.post(
        "/labs/import-csv",
        headers=headers,
        data={"csrf_token": "forged", "drawn_on": "2026-11-08"},
        files={"csv_file": ("bad.csv", b"bad\\n", "text/csv")},
        follow_redirects=False,
    )
    assert forged.status_code == 403


def test_522_proxy_signed_multipart_header_succeeds_without_form_field(
    proxy_client522,
):
    client, token = proxy_client522
    accepted = client.post(
        "/labs/import-csv",
        headers={
            "Origin": "https://tracker.example",
            "Sec-Fetch-Site": "same-origin",
            HEADER_NAME: token,
        },
        data={"drawn_on": "2026-11-08"},
        files={"csv_file": ("bad.csv", b"bad\\n", "text/csv")},
        follow_redirects=False,
    )
    assert accepted.status_code != 403
    assert accepted.headers["x-tracker-csrf-report"] == "valid"


def test_522_proxy_unsigned_legacy_client_without_origin_unchanged(proxy_client522):
    client, token = proxy_client522
    # No browser metadata and no Origin is not a proxy-mismatch exception.
    # The original report-only legacy behavior is retained.
    result = client.post(
        "/vitals",
        data=_form522("QA legacy Vitals 522"),
        follow_redirects=False,
    )
    assert result.status_code == 303


@pytest.mark.parametrize("method", ("GET", "HEAD", "OPTIONS"))
def test_522_safe_methods_do_not_use_proxy_bypass(method):
    assert not allow_signed_proxy_write522(
        method,
        {"origin": "https://tracker.example", "sec-fetch-site": "same-origin"},
        "valid",
    )


def test_522_duplicate_origin_and_csrf_headers_refused():
    origin_headers = Headers(raw=[
        (b"origin", b"https://tracker.example"),
        (b"origin", b"https://attacker.example"),
        (b"sec-fetch-site", b"same-origin"),
    ])
    assert not allow_signed_proxy_write522("POST", origin_headers, "valid")

    csrf_headers = Headers(raw=[
        (b"origin", b"https://tracker.example"),
        (b"sec-fetch-site", b"same-origin"),
        (b"x-tracker-csrf", b"signed"),
        (b"x-tracker-csrf", b"forged"),
    ])
    assert not allow_signed_proxy_write522("POST", csrf_headers, "valid")
