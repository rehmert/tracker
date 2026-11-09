"""Release 520: optional strict CSRF supports native multipart form uploads.

Tests use only TestClient requests, temporary signing keys, and in-memory
uploads; no real user data, live file stores or public HTTP calls.
"""
import pytest
from fastapi import Depends, FastAPI, File, UploadFile
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app import config, session_auth385
from app.db import SessionLocal
from app.models import Compound
from app.csrf_enforcement520 import (
    SIGNED_SESSION_POST_PATHS520,
    enforce_multipart_csrf520,
    owns_signed_csrf520,
)
from app.csrf_reporting import REPORT_HEADER
from app.csrf_runtime import COOKIE_NAME, HEADER_NAME, load_key
from app.csrf_tokens import issue_token
from app.main import app


@pytest.fixture
def strict_client520(monkeypatch, tmp_path):
    monkeypatch.setenv("TRACKER_CSRF_ENFORCE", "1")
    monkeypatch.setattr(config, "AUTH_USER", "")
    monkeypatch.setattr(config, "AUTH_PASS", "")
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    with TestClient(app) as client:
        yield client


def _token520(client):
    page = client.get("/labs")
    assert page.status_code == 200
    token = page.cookies[COOKIE_NAME]
    assert token
    return token


def _multipart_compound520(client, *, data=None, headers=None):
    return client.post(
        "/compounds",
        data={"name": "", **(data or {})},
        files={"ignored_attachment": ("test.txt", b"test", "text/plain")},
        headers=headers or {},
        follow_redirects=False,
    )


def _compound_count520(name):
    # Query the conftest-isolated SQLite database directly. The /compounds
    # search form echoes its q parameter even if no such record exists.
    with SessionLocal() as db:
        return db.scalar(
            select(func.count()).select_from(Compound)
            .where(Compound.name == name)
        )


def test_520_strict_denied_multipart_cannot_create_compound(strict_client520):
    client = strict_client520
    _token520(client)
    name = "520 forbidden compound"
    before = _compound_count520(name)
    response = _multipart_compound520(client, data={"name": name})
    assert response.status_code == 403
    assert _compound_count520(name) == before == 0


def test_520_strict_signed_multipart_can_create_isolated_compound(
    strict_client520,
):
    client = strict_client520
    token = _token520(client)
    name = "520 signed native compound"
    before = _compound_count520(name)
    response = _multipart_compound520(
        client, data={"name": name, "csrf_token": token},
    )
    assert response.status_code == 303
    assert response.headers[REPORT_HEADER] == "valid"
    assert _compound_count520(name) == before + 1


def test_520_strict_missing_multipart_token_denied(strict_client520):
    client = strict_client520
    _token520(client)
    response = _multipart_compound520(client)
    assert response.status_code == 403
    assert "CSRF token required" in response.text
    assert response.headers[REPORT_HEADER] == "form-uninspected"


def test_520_strict_valid_native_multipart_form_field_reaches_endpoint(
    strict_client520,
):
    client = strict_client520
    token = _token520(client)
    response = _multipart_compound520(client, data={"csrf_token": token})
    assert response.status_code == 422  # Missing required compound name
    assert response.headers[REPORT_HEADER] == "valid"


@pytest.mark.parametrize("bad", ["invalid", "", "broken-token"])
def test_520_strict_invalid_multipart_form_field_denied(strict_client520, bad):
    client = strict_client520
    _token520(client)
    response = _multipart_compound520(client, data={"csrf_token": bad})
    assert response.status_code == 403


def test_520_strict_signed_field_requires_matching_cookie(strict_client520):
    client = strict_client520
    token = _token520(client)
    client.cookies.delete(COOKIE_NAME)
    response = _multipart_compound520(client, data={"csrf_token": token})
    assert response.status_code == 403


def test_520_strict_signing_key_unavailable_fails_closed(
    strict_client520, monkeypatch,
):
    client = strict_client520
    token = _token520(client)

    def missing_key():
        raise ValueError("simulated missing key; must not be exposed")

    monkeypatch.setattr("app.csrf_enforcement520.load_key", missing_key)
    response = _multipart_compound520(client, data={"csrf_token": token})
    assert response.status_code == 503
    assert "simulated missing key" not in response.text


def test_520_strict_duplicate_form_tokens_denied(strict_client520):
    client = strict_client520
    token = _token520(client)
    response = client.post(
        "/compounds",
        files=[
            ("csrf_token", (None, token)),
            ("csrf_token", (None, token)),
            ("ignored_attachment", ("test.txt", b"test", "text/plain")),
        ],
        follow_redirects=False,
    )
    assert response.status_code == 403


def test_520_strict_header_allows_multipart_upload_without_form_token(
    strict_client520,
):
    client = strict_client520
    token = _token520(client)
    response = _multipart_compound520(
        client, headers={HEADER_NAME: token},
    )
    assert response.status_code == 422
    assert response.headers[REPORT_HEADER] == "valid"


def test_520_strict_invalid_header_cannot_be_overridden_by_valid_form(
    strict_client520,
):
    client = strict_client520
    token = _token520(client)
    response = _multipart_compound520(
        client, data={"csrf_token": token},
        headers={HEADER_NAME: token + "forged"},
    )
    assert response.status_code == 403
    assert response.headers[REPORT_HEADER] == "invalid"


def test_520_strict_foreign_origin_still_rejected_before_multipart(
    strict_client520,
):
    client = strict_client520
    token = _token520(client)
    response = _multipart_compound520(
        client, data={"csrf_token": token},
        headers={"Origin": "https://attacker.example"},
    )
    assert response.status_code == 403
    assert response.text == "Cross-origin write request denied."


def test_520_strict_multipart_file_reaches_real_upload_route(
    strict_client520,
):
    client = strict_client520
    token = _token520(client)
    # Invalid CSV content should reach the CSV import parser, not be blocked
    # by CSRF. The test does not persist an uploaded file or lab report.
    response = client.post(
        "/labs/import-csv",
        data={
            "csrf_token": token,
            "drawn_on": "2026-11-09",
            "lab_name": "isolated upload QA",
        },
        files={"csv_file": ("invalid.csv", b"this is not a CSV\n", "text/csv")},
        follow_redirects=False,
    )
    assert response.status_code != 403
    assert response.headers[REPORT_HEADER] == "valid"


def test_520_strict_urlencoded_behavior_unchanged(strict_client520):
    client = strict_client520
    token = _token520(client)
    invalid = client.post(
        "/compounds", data={"name": ""}, follow_redirects=False,
    )
    assert invalid.status_code == 403
    allowed = client.post(
        "/compounds",
        data={"name": "", "csrf_token": token},
        follow_redirects=False,
    )
    assert allowed.status_code == 422
    assert allowed.headers[REPORT_HEADER] == "valid"


def test_520_strict_json_requires_header(strict_client520):
    client = strict_client520
    token = _token520(client)
    missing = client.post("/pk/compounds", json={}, follow_redirects=False)
    assert missing.status_code == 403
    allowed = client.post(
        "/pk/compounds", json={},
        headers={HEADER_NAME: token},
        follow_redirects=False,
    )
    assert allowed.status_code != 403
    assert allowed.headers[REPORT_HEADER] == "valid"


def test_520_report_only_multipart_compatibility(monkeypatch, tmp_path):
    monkeypatch.setenv("TRACKER_CSRF_ENFORCE", "0")
    monkeypatch.setattr(config, "AUTH_USER", "")
    monkeypatch.setattr(config, "AUTH_PASS", "")
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    with TestClient(app) as client:
        _token520(client)
        response = _multipart_compound520(client)
        assert response.status_code == 422
        assert response.headers[REPORT_HEADER] == "form-uninspected"


def test_520_route_dependency_keeps_upload_readable_after_csrf_check(
    monkeypatch, tmp_path,
):
    """Verify route-level CSRF doesn't close the uploaded stream early."""
    monkeypatch.setenv("TRACKER_CSRF_ENFORCE", "1")
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    local = FastAPI(dependencies=[Depends(enforce_multipart_csrf520)])

    @local.post("/upload")
    async def upload(file: UploadFile = File(...)):
        raw = await file.read()
        return {"size": len(raw), "filename": file.filename}

    token = issue_token(load_key())
    with TestClient(local) as client:
        client.cookies.set(COOKIE_NAME, token)
        result = client.post(
            "/upload",
            data={"csrf_token": token},
            files={"file": ("test.txt", b"upload data readable", "text/plain")},
        )
        assert result.status_code == 200
        assert result.json() == {
            "size": len(b"upload data readable"),
            "filename": "test.txt",
        }
        denied = client.post(
            "/upload", files={"file": ("test.txt", b"never read", "text/plain")},
        )
        assert denied.status_code == 403


def test_520_existing_signed_session_routes_are_not_double_gated(monkeypatch):
    from starlette.requests import Request

    monkeypatch.setattr(session_auth385, "enabled", lambda: True)
    for path in SIGNED_SESSION_POST_PATHS520:
        request = Request({
            "type": "http",
            "method": "POST",
            "path": path,
            "query_string": b"",
            "headers": [],
        })
        assert owns_signed_csrf520(request)


def test_520_does_not_claim_multipart_body_was_inspected_in_report_mode(
    monkeypatch, tmp_path,
):
    monkeypatch.setenv("TRACKER_CSRF_ENFORCE", "0")
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(config, "AUTH_USER", "")
    monkeypatch.setattr(config, "AUTH_PASS", "")
    with TestClient(app) as client:
        token = _token520(client)
        response = _multipart_compound520(
            client, data={"csrf_token": token},
        )
        assert response.status_code == 422
        assert response.headers[REPORT_HEADER] == "form-uninspected"
