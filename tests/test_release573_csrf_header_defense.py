"""Release 573: ambiguous-header defense and strict/report-only compatibility.

Uses pytest's isolated Tracker database, disposable CSRF keys, and TestClient.
No real DEV/PROD service or browser network requests are made.
"""
from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient
from starlette.datastructures import Headers

from app import config
from app.csrf_runtime import COOKIE_NAME, HEADER_NAME
from app.main import app
from app.proxy_origin522 import allow_signed_proxy_write522
from app.request_origin import reject_cross_origin_write


@pytest.fixture
def client573(monkeypatch, tmp_path, request):
    strict = request.param
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(config, "AUTH_USER", "")
    monkeypatch.setattr(config, "AUTH_PASS", "")
    monkeypatch.setenv("TRACKER_ORIGIN_GUARD", "1")
    monkeypatch.setenv("TRACKER_CSRF_ENFORCE", "1" if strict else "0")
    with TestClient(app) as client:
        page = client.get("/compounds")
        assert page.status_code == 200
        token = client.cookies.get(COOKIE_NAME)
        assert token and token.startswith("v1.")
        yield client, token


@pytest.mark.parametrize("client573", [False, True], indirect=True)
@pytest.mark.parametrize("bad", ["forged", "same"])
def test_573_duplicate_csrf_header_is_invalid_even_when_one_signed(
    client573, bad,
):
    client, token = client573
    submitted = token if bad == "same" else "forged"
    response = client.post(
        "/compounds",
        data={"name": ""},
        headers=[
            (HEADER_NAME, token),
            (HEADER_NAME.lower(), submitted),
        ],
        follow_redirects=False,
    )
    assert response.headers.get("x-tracker-csrf-report") == "invalid"
    strict = os.environ["TRACKER_CSRF_ENFORCE"] == "1"
    assert response.status_code == (403 if strict else 422)


@pytest.mark.parametrize("client573", [False, True], indirect=True)
def test_573_blank_header_never_falls_back_to_valid_form_field(client573):
    client, token = client573
    response = client.post(
        "/compounds",
        data={"name": "", "csrf_token": token},
        headers={HEADER_NAME: ""},
        follow_redirects=False,
    )
    assert response.headers.get("x-tracker-csrf-report") == "invalid"
    strict = os.environ["TRACKER_CSRF_ENFORCE"] == "1"
    assert response.status_code == (403 if strict else 422)


@pytest.mark.parametrize("field", ("host", "origin", "sec-fetch-site"))
def test_573_duplicate_browser_metadata_is_denied_for_writes(field):
    headers = Headers(raw=[
        (b"host", b"tracker.example"),
        (b"origin", b"https://tracker.example"),
        (b"sec-fetch-site", b"same-origin"),
        (field.encode("ascii"), b"mismatched.example"),
    ])
    for method in ("POST", "PUT", "PATCH", "DELETE"):
        assert reject_cross_origin_write(method, headers)
    for method in ("GET", "HEAD", "OPTIONS"):
        assert not reject_cross_origin_write(method, headers)


def test_573_proxy_exception_cannot_override_duplicate_fetch_site():
    headers = Headers(raw=[
        (b"host", b"tracker-internal:8000"),
        (b"origin", b"https://tracker.example"),
        (b"sec-fetch-site", b"same-origin"),
        (b"sec-fetch-site", b"same-origin"),
        (b"x-tracker-csrf", b"valid"),
    ])
    assert reject_cross_origin_write("POST", headers)
    assert not allow_signed_proxy_write522("POST", headers, "valid")


@pytest.mark.parametrize("client573", [False, True], indirect=True)
def test_573_duplicate_origin_blocked_before_csrf_or_form_validation(client573):
    client, token = client573
    response = client.post(
        "/compounds",
        data={"name": "", "csrf_token": token},
        headers=[
            ("Origin", "http://testserver"),
            ("Origin", "https://attacker.example"),
            ("Sec-Fetch-Site", "same-origin"),
        ],
        follow_redirects=False,
    )
    assert response.status_code == 403
    assert response.text == "Cross-origin write request denied."


@pytest.mark.parametrize("client573", [False, True], indirect=True)
def test_573_duplicate_fetch_metadata_blocked_even_with_signed_header(client573):
    client, token = client573
    response = client.post(
        "/compounds",
        data={"name": ""},
        headers=[
            (HEADER_NAME, token),
            ("Origin", "http://testserver"),
            ("Sec-Fetch-Site", "same-origin"),
            ("Sec-Fetch-Site", "cross-site"),
        ],
        follow_redirects=False,
    )
    assert response.status_code == 403
    assert response.text == "Cross-origin write request denied."


@pytest.mark.parametrize("client573", [False, True], indirect=True)
def test_573_single_signed_header_still_reaches_validation(client573):
    client, token = client573
    response = client.post(
        "/compounds",
        data={"name": ""},
        headers={HEADER_NAME: token, "Origin": "http://testserver"},
        follow_redirects=False,
    )
    assert response.status_code == 422
    assert response.headers["x-tracker-csrf-report"] == "valid"


@pytest.mark.parametrize("client573", [False, True], indirect=True)
def test_573_signed_header_supports_large_urlencoded_body(client573):
    client, token = client573
    response = client.post(
        "/compounds",
        data={"name": "", "notes": "x" * 70000},
        headers={HEADER_NAME: token},
        follow_redirects=False,
    )
    assert response.status_code == 422
    assert response.headers["x-tracker-csrf-report"] == "valid"
