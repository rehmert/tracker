"""Hotfix 492: protect Food browser writes behind a TLS reverse proxy.

All middleware checks use the actual Tracker FastAPI app. The success case
reaches Food endpoint validation but never inserts a food record.
"""

import pytest
from fastapi.testclient import TestClient

from app import config
from app.csrf_runtime import COOKIE_NAME, HEADER_NAME
from app.food_origin492 import (
    allow_food_proxy_write492, is_food_write492,
)
from app.main import app


@pytest.mark.parametrize("path", (
    "/food/entry", "/food/water", "/food/targets", "/food/photo",
    "/food/template/save", "/food/quick/21", "/food/favorite/7",
    "/food/water/12/delete", "/food/entry/3/delete",
    "/food/entry/31/edit", "/food/entry/4/nutrition",
    "/food/template/5/log", "/food/template/5/rename",
    "/food/template/5/delete",
))
def test_exact_food_routes_are_allowlisted(path):
    assert is_food_write492(path)


@pytest.mark.parametrize("path", (
    "/food", "/food/entry/-1/delete", "/food/entry/0/edit",
    "/food/entry/4/export", "/food/quick/7/mutate",
    "/food/entry/00000000000/edit", "/foodly/entry",
    "/account/password", "/login", "/compounds", "/doses",
    "/secondary/full/food/entry", "/food/template/1/run",
))
def test_other_routes_do_not_gain_exception(path):
    assert not is_food_write492(path)


@pytest.mark.parametrize("origin,fetch_site,csrf_report,accepted", (
    ("https://tracker.example", "same-origin", "valid", True),
    ("https://tracker.example:8443", "same-origin", "valid", True),
    ("https://tracker.example", "cross-site", "valid", False),
    ("https://tracker.example", "same-site", "valid", False),
    ("https://tracker.example", "", "valid", False),
    ("http://tracker.example", "same-origin", "valid", False),
    ("null", "same-origin", "valid", True),
    ("null", "cross-site", "valid", False),
    ("null", "same-site", "valid", False),
    ("null", "", "valid", False),
    ("null", "same-origin", "invalid", False),
    ("null", "same-origin", "missing", False),
    ("null", "same-origin", "form-uninspected", False),
    ("NULL", "same-origin", "valid", False),
    ("null ", "same-origin", "valid", False),
    ("https://attacker.example/path", "same-origin", "valid", False),
    ("https://user@tracker.example", "same-origin", "valid", False),
    ("https://tracker.example", "same-origin", "invalid", False),
    ("https://tracker.example", "same-origin", "missing", False),
    ("https://tracker.example", "same-origin", "form-uninspected", False),
))
def test_all_four_proxy_constraints(origin, fetch_site, csrf_report, accepted):
    assert allow_food_proxy_write492(
        "POST", "/food/entry",
        {"origin": origin, "sec-fetch-site": fetch_site},
        csrf_report,
    ) is accepted


def test_no_method_or_other_route_exemption():
    headers = {
        "origin": "https://tracker.example",
        "sec-fetch-site": "same-origin",
    }
    for method in ("GET", "PUT", "PATCH", "DELETE"):
        assert not allow_food_proxy_write492(
            method, "/food/entry", headers, "valid",
        )
    assert not allow_food_proxy_write492(
        "POST", "/compounds", headers, "valid",
    )


@pytest.fixture
def reverse_proxy_client(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "AUTH_USER", "")
    monkeypatch.setattr(config, "AUTH_PASS", "")
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    monkeypatch.setenv("TRACKER_INSTANCE", "PROD")
    monkeypatch.setenv("TRACKER_ORIGIN_GUARD", "1")
    monkeypatch.setenv("TRACKER_CSRF_ENFORCE", "0")

    with TestClient(
        app, base_url="http://tracker-internal:8000",
    ) as client:
        page = client.get("/")
        assert page.status_code == 200
        csrf_token = client.cookies.get(COOKIE_NAME)
        assert csrf_token
        yield client, csrf_token


def test_real_proxy_food_post_reaches_validation(reverse_proxy_client):
    client, token = reverse_proxy_client
    response = client.post(
        "/food/entry",
        headers={
            "Origin": "https://tracker.example",
            "Sec-Fetch-Site": "same-origin",
            HEADER_NAME: token,
        },
        data={"name": ""},
        follow_redirects=False,
    )
    # Invalid empty food name: endpoint reached, no food record inserted.
    assert response.status_code == 422
    assert response.headers["x-tracker-csrf-report"] == "valid"


def test_real_null_origin_signed_header_reaches_food_validation(reverse_proxy_client):
    """Model the exact production browser request and prove route reachability."""
    client, token = reverse_proxy_client
    response = client.post(
        "/food/entry",
        headers={
            "Origin": "null",
            "Sec-Fetch-Site": "same-origin",
            HEADER_NAME: token,
        },
        data={"name": ""},
        follow_redirects=False,
    )
    assert response.status_code == 422
    assert response.headers["x-tracker-csrf-report"] == "valid"


def test_real_null_origin_signed_form_reaches_food_validation(reverse_proxy_client):
    """Ordinary HTML form with only signed hidden field also succeeds."""
    client, token = reverse_proxy_client
    response = client.post(
        "/food/entry",
        headers={
            "Origin": "null",
            "Sec-Fetch-Site": "same-origin",
        },
        data={"name": "", "csrf_token": token},
        follow_redirects=False,
    )
    assert response.status_code == 422
    assert response.headers["x-tracker-csrf-report"] == "valid"


def test_real_proxy_signed_form_field_is_sufficient(reverse_proxy_client):
    client, token = reverse_proxy_client
    response = client.post(
        "/food/entry",
        headers={
            "Origin": "https://tracker.example",
            "Sec-Fetch-Site": "same-origin",
        },
        data={"name": "", "csrf_token": token},
        follow_redirects=False,
    )
    assert response.status_code == 422


@pytest.mark.parametrize("headers,expected", (
    ({"Origin": "https://tracker.example",
      "Sec-Fetch-Site": "same-origin",
      HEADER_NAME: "forged"}, 403),
    ({"Origin": "https://tracker.example",
      "Sec-Fetch-Site": "cross-site"}, 403),
    ({"Origin": "https://tracker.example",
      "Sec-Fetch-Site": "same-site"}, 403),
    ({"Origin": "http://tracker.example",
      "Sec-Fetch-Site": "same-origin"}, 403),
    ({"Origin": "null",
      "Sec-Fetch-Site": "cross-site"}, 403),
    ({"Origin": "null",
      "Sec-Fetch-Site": "same-site"}, 403),
    ({"Origin": "null",
      "Sec-Fetch-Site": "same-origin",
      HEADER_NAME: "forged"}, 403),
    ({"Origin": "https://tracker.example",
      "Sec-Fetch-Site": "same-origin",
      HEADER_NAME: "forged"}, 403),
))
def test_real_proxy_rejects_unsafe_or_unsigned(reverse_proxy_client, headers, expected):
    client, token = reverse_proxy_client
    sent = {HEADER_NAME: token, **headers}
    response = client.post(
        "/food/entry", headers=sent,
        data={"name": ""},
        follow_redirects=False,
    )
    assert response.status_code == expected


@pytest.mark.parametrize("origin", ("https://tracker.example", "null"))
def test_missing_csrf_does_not_receive_proxy_exception(reverse_proxy_client, origin):
    client, token = reverse_proxy_client
    response = client.post(
        "/food/entry",
        headers={
            "Origin": origin,
            "Sec-Fetch-Site": "same-origin",
        },
        data={"name": ""},
        follow_redirects=False,
    )
    assert response.status_code == 403


@pytest.mark.parametrize("origin", ("https://tracker.example", "null"))
def test_522_other_routes_accept_proxy_mismatch_only_with_signed_proof(
    reverse_proxy_client, origin,
):
    """Release 522 supersedes Food-only bypass for signed browser writes."""
    client, token = reverse_proxy_client
    allow = client.post(
        "/compounds",
        headers={
            "Origin": origin,
            "Sec-Fetch-Site": "same-origin",
            HEADER_NAME: token,
        },
        data={},
        follow_redirects=False,
    )
    # Reached router's missing-name validation; no record created.
    assert allow.status_code == 422
    assert allow.headers["x-tracker-csrf-report"] == "valid"

    for headers in (
        {"Origin": origin, "Sec-Fetch-Site": "same-origin"},
        {"Origin": origin, "Sec-Fetch-Site": "same-origin",
         HEADER_NAME: "forged"},
        {"Origin": origin, "Sec-Fetch-Site": "cross-site",
         HEADER_NAME: token},
        {"Origin": origin, "Sec-Fetch-Site": "same-site",
         HEADER_NAME: token},
    ):
        denied = client.post(
            "/compounds", headers=headers, data={},
            follow_redirects=False,
        )
        assert denied.status_code == 403
