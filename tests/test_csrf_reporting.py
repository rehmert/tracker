"""CSRF report-only rollout and request compatibility."""

import pytest
from fastapi.testclient import TestClient

from app import config
from app.csrf_reporting import REPORT_HEADER
from app.csrf_runtime import COOKIE_NAME
from app.main import app


@pytest.fixture
def client(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "AUTH_USER", "")
    monkeypatch.setattr(config, "AUTH_PASS", "")
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)

    with TestClient(app) as instance:
        yield instance


def test_html_get_issues_token_without_report(client):
    response = client.get("/labs")
    assert response.status_code == 200
    assert COOKIE_NAME in response.cookies
    assert REPORT_HEADER not in response.headers


def test_valid_signed_header_is_reported(client):
    page = client.get("/labs")
    token = page.cookies[COOKIE_NAME]

    response = client.post(
        "/compounds",
        headers={"X-Tracker-CSRF": token},
        data={},
        follow_redirects=False,
    )

    assert response.status_code == 422
    assert response.headers[REPORT_HEADER] == "valid"


def test_tampered_header_is_reported_not_rejected(client):
    page = client.get("/labs")
    token = page.cookies[COOKIE_NAME]

    response = client.post(
        "/compounds",
        headers={"X-Tracker-CSRF": token + "broken"},
        data={},
        follow_redirects=False,
    )

    assert response.status_code == 422
    assert response.headers[REPORT_HEADER] == "invalid"


def test_missing_json_token_is_reported(client):
    response = client.post(
        "/pk/compounds",
        json={},
        follow_redirects=False,
    )

    assert response.headers[REPORT_HEADER] == "missing"
    assert response.status_code != 403


def test_urlencoded_form_without_header_is_uninspected(client):
    # An actual URL-encoded form body must be present.
    # data={} has no content type in the HTTP test client.
    response = client.post(
        "/compounds",
        data={"name": ""},
        follow_redirects=False,
    )

    assert response.status_code == 422
    assert response.headers[
        REPORT_HEADER
    ] == "form-uninspected"


def test_explicit_urlencoded_content_type_is_uninspected(client):
    response = client.post(
        "/compounds",
        content="name=",
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
        },
        follow_redirects=False,
    )

    assert response.status_code == 422
    assert response.headers[
        REPORT_HEADER
    ] == "form-uninspected"


def test_empty_body_without_content_type_is_missing(client):
    response = client.post(
        "/compounds",
        data={},
        follow_redirects=False,
    )

    assert response.status_code == 422
    assert response.headers[REPORT_HEADER] == "missing"


def test_multipart_form_without_header_is_uninspected(client):
    response = client.post(
        "/compounds",
        files={
            "placeholder": (
                "empty.txt",
                b"",
                "text/plain",
            )
        },
        follow_redirects=False,
    )

    assert response.status_code == 422
    assert response.headers[
        REPORT_HEADER
    ] == "form-uninspected"


def test_cookie_missing_when_header_present(client):
    from app.csrf_runtime import load_key
    from app.csrf_tokens import issue_token

    token = issue_token(load_key())

    response = client.post(
        "/compounds",
        headers={"X-Tracker-CSRF": token},
        data={},
        follow_redirects=False,
    )

    assert response.status_code == 422
    assert response.headers[REPORT_HEADER] == "missing"


def test_cross_origin_guard_still_rejects(client):
    response = client.post(
        "/compounds",
        headers={
            "Origin": "https://attacker.example",
            "X-Tracker-CSRF": "invalid",
        },
        data={},
        follow_redirects=False,
    )

    assert response.status_code == 403
    assert REPORT_HEADER not in response.headers
    assert response.headers["x-frame-options"] == "DENY"


def test_normal_get_remains_unreported(client):
    response = client.get("/healthz")

    assert response.status_code == 200
    assert REPORT_HEADER not in response.headers


def test_report_contains_no_secret_or_token(client):
    page = client.get("/labs")
    token = page.cookies[COOKIE_NAME]

    response = client.post(
        "/compounds",
        headers={"X-Tracker-CSRF": token},
        data={},
        follow_redirects=False,
    )

    assert token not in response.headers[REPORT_HEADER]
    assert response.headers[REPORT_HEADER] == "valid"


def test_csrf_report_preserves_security_headers(client):
    response = client.post(
        "/compounds",
        data={},
        follow_redirects=False,
    )

    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers[
        "x-content-type-options"
    ] == "nosniff"
    assert response.headers[
        "cache-control"
    ] == "private, no-store"


def test_reporter_never_reads_body():
    from pathlib import Path

    source = Path(
        "app/csrf_reporting.py"
    ).read_text()

    assert "request.body(" not in source
    assert "request.form(" not in source
    assert "request.json(" not in source
