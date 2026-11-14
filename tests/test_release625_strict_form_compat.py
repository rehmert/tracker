"""Release 625 consolidated Phase 1: native/multipart strict-mode compatibility.

All writes use intentionally INVALID business payloads so the test cannot
mutate inventory or health records. Strict mode is scoped to this fixture;
production defaults are not modified. These tests cover representative
paths, not every route or browser upload workflow.
"""
import pytest
from fastapi.testclient import TestClient

from app import config
from app.csrf_runtime import COOKIE_NAME, HEADER_NAME
from app.csrf_reporting import REPORT_HEADER
from app.main import app


@pytest.fixture
def strict_client(monkeypatch, tmp_path):
    monkeypatch.setenv("TRACKER_CSRF_ENFORCE", "1")
    monkeypatch.setattr(config, "AUTH_USER", "")
    monkeypatch.setattr(config, "AUTH_PASS", "")
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    with TestClient(app) as client:
        yield client


def signed_cookie(strict_client):
    response = strict_client.get("/labs")
    assert response.status_code == 200
    token = response.cookies[COOKIE_NAME]
    assert token
    return token


def test_625_urlencoded_missing_token_denied_before_route_validation(strict_client):
    response = strict_client.post("/compounds", data={"name": ""},
                                  follow_redirects=False)
    assert response.status_code == 403
    assert response.headers[REPORT_HEADER] == "missing"


def test_625_urlencoded_valid_header_reaches_validation(strict_client):
    token = signed_cookie(strict_client)
    response = strict_client.post(
        "/compounds", data={"name": ""},
        headers={HEADER_NAME: token}, follow_redirects=False,
    )
    assert response.status_code == 422
    assert response.headers[REPORT_HEADER] == "valid"


def test_625_multipart_missing_token_denied_without_write(strict_client):
    response = strict_client.post(
        "/compounds",
        files={"placeholder": ("empty.txt", b"", "text/plain")},
        follow_redirects=False,
    )
    assert response.status_code == 403


def test_625_multipart_signed_header_reaches_route_validation(strict_client):
    token = signed_cookie(strict_client)
    response = strict_client.post(
        "/compounds",
        files={"placeholder": ("empty.txt", b"", "text/plain")},
        headers={HEADER_NAME: token}, follow_redirects=False,
    )
    assert response.status_code == 422
    assert response.headers[REPORT_HEADER] == "valid"


def test_625_multipart_native_signed_field_reaches_validation(strict_client):
    token = signed_cookie(strict_client)
    response = strict_client.post(
        "/compounds",
        data={"csrf_token": token},
        files={"placeholder": ("empty.txt", b"", "text/plain")},
        follow_redirects=False,
    )
    assert response.status_code == 422
    assert response.headers[REPORT_HEADER] == "valid"


def test_625_multipart_duplicate_field_rejected(strict_client):
    token = signed_cookie(strict_client)
    response = strict_client.post(
        "/compounds",
        data=[("csrf_token", token), ("csrf_token", token)],
        files={"placeholder": ("empty.txt", b"", "text/plain")},
        follow_redirects=False,
    )
    assert response.status_code == 403


def test_625_cross_origin_rejected_even_with_signed_header(strict_client):
    token = signed_cookie(strict_client)
    response = strict_client.post(
        "/compounds", data={"name": ""},
        headers={HEADER_NAME: token, "Origin": "https://attacker.example"},
        follow_redirects=False,
    )
    assert response.status_code == 403
    assert "Cross-origin" in response.text


def test_625_strict_fixture_does_not_change_default_source():
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    source = (root / "app" / "main.py").read_text(encoding="utf-8")
    assert 'os.environ.get("TRACKER_CSRF_ENFORCE", "0")' in source
