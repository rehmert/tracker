"""Report-only verification of URL-encoded form CSRF fields."""

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


def get_token(client):
    page = client.get("/labs")
    assert page.status_code == 200
    return page.cookies[COOKIE_NAME]


def test_valid_urlencoded_field(client):
    token = get_token(client)
    response = client.post(
        "/compounds",
        data={
            "name": "",
            "csrf_token": token,
        },
        follow_redirects=False,
    )
    assert response.status_code == 422
    assert response.headers[REPORT_HEADER] == "valid"


def test_tampered_urlencoded_field(client):
    token = get_token(client)
    response = client.post(
        "/compounds",
        data={
            "name": "",
            "csrf_token": token + "tampered",
        },
        follow_redirects=False,
    )
    assert response.status_code == 422
    assert response.headers[REPORT_HEADER] == "invalid"


def test_missing_urlencoded_field(client):
    get_token(client)
    response = client.post(
        "/compounds",
        data={"name": ""},
        follow_redirects=False,
    )
    assert response.status_code == 422
    assert response.headers[REPORT_HEADER] == "missing"


def test_duplicate_form_tokens_rejected_for_reporting(client):
    token = get_token(client)
    body = (
        "name=&csrf_token=" + token
        + "&csrf_token=" + token
    )
    response = client.post(
        "/compounds",
        content=body,
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
        },
        follow_redirects=False,
    )
    assert response.status_code == 422
    assert response.headers[REPORT_HEADER] == "invalid"


def test_form_payload_reaches_endpoint_unchanged(client):
    token = get_token(client)
    response = client.post(
        "/compounds",
        data={
            "name": "",
            "category": "peptide",
            "csrf_token": token,
        },
        follow_redirects=False,
    )

    # FastAPI sees the empty name and rejects it as before.
    assert response.status_code == 422
    assert response.headers[REPORT_HEADER] == "valid"


def test_form_with_no_cookie_is_missing(client):
    from app.csrf_runtime import load_key
    from app.csrf_tokens import issue_token

    token = issue_token(load_key())
    response = client.post(
        "/compounds",
        data={
            "name": "",
            "csrf_token": token,
        },
        follow_redirects=False,
    )
    assert response.status_code == 422
    assert response.headers[REPORT_HEADER] == "missing"


def test_large_urlencoded_body_not_inspected(client):
    token = get_token(client)
    response = client.post(
        "/compounds",
        data={
            "name": "",
            "notes": "x" * (65 * 1024),
            "csrf_token": token,
        },
        follow_redirects=False,
    )
    assert response.status_code == 422
    assert response.headers[
        REPORT_HEADER
    ] == "form-uninspected"


def test_multipart_still_uninspected(client):
    get_token(client)
    response = client.post(
        "/compounds",
        files={
            "placeholder": (
                "sample.txt",
                b"test content",
                "text/plain",
            )
        },
        follow_redirects=False,
    )
    assert response.status_code == 422
    assert response.headers[
        REPORT_HEADER
    ] == "form-uninspected"


def test_cross_origin_still_rejected(client):
    token = get_token(client)
    response = client.post(
        "/compounds",
        headers={"Origin": "https://evil.example"},
        data={
            "name": "",
            "csrf_token": token,
        },
        follow_redirects=False,
    )
    assert response.status_code == 403
    assert REPORT_HEADER not in response.headers
