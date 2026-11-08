"""Release 500: exact Labs proxy-origin carveout and CSRF boundary."""

import pytest
from fastapi.testclient import TestClient

from app import config
from app.csrf_runtime import COOKIE_NAME, HEADER_NAME
from app.labs_origin500 import is_lab_write500, allow_lab_proxy_write500
from app.main import app


@pytest.mark.parametrize("path", (
    "/labs", "/labs/import-csv", "/labs/1/results",
    "/labs/2/import-csv", "/labs/13/edit", "/labs/77/delete",
    "/lab-results/9/edit", "/lab-results/99/delete",
))
def test_500_only_intended_labs_writes_have_proxy_fallback(path):
    assert is_lab_write500(path)


@pytest.mark.parametrize("path", (
    "/labs/new", "/labs/trends/tsh", "/labs/trends/tsh/export.csv",
    "/labs/0/results", "/labs/-1/delete", "/labs/1/special",
    "/lab-results/0/delete", "/lab-results/1/mutate",
    "/compounds", "/food/entry", "/secondary/food/entry",
    "/account/password", "/login",
))
def test_500_other_paths_cannot_use_labs_fallback(path):
    assert not is_lab_write500(path)


@pytest.mark.parametrize("origin,fetch_site,csrf,allowed", (
    ("null", "same-origin", "valid", True),
    ("https://tracker.example", "same-origin", "valid", True),
    ("https://tracker.example:8443", "same-origin", "valid", True),
    ("http://tracker.example", "same-origin", "valid", False),
    ("null", "cross-site", "valid", False),
    ("null", "same-site", "valid", False),
    ("null", "", "valid", False),
    ("null", "same-origin", "missing", False),
    ("null", "same-origin", "invalid", False),
    ("null", "same-origin", "form-uninspected", False),
    ("NULL", "same-origin", "valid", False),
    ("null ", "same-origin", "valid", False),
    ("https://attacker.example/path", "same-origin", "valid", False),
    ("https://user@attacker.example", "same-origin", "valid", False),
    ("https://tracker.example", "same-site", "valid", False),
    ("https://tracker.example", "same-origin", "invalid", False),
))
def test_500_all_labs_proxy_requirements(origin, fetch_site, csrf, allowed):
    assert allow_lab_proxy_write500(
        "POST", "/labs",
        {"origin": origin, "sec-fetch-site": fetch_site}, csrf
    ) is allowed


def test_500_no_get_or_unlisted_route_exception():
    h = {"origin": "null", "sec-fetch-site": "same-origin"}
    for method in ("GET", "PUT", "PATCH", "DELETE"):
        assert not allow_lab_proxy_write500(method, "/labs", h, "valid")
    assert not allow_lab_proxy_write500(
        "POST", "/compounds", h, "valid"
    )


@pytest.fixture
def isolated_app(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "AUTH_USER", "")
    monkeypatch.setattr(config, "AUTH_PASS", "")
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    monkeypatch.setenv("TRACKER_INSTANCE", "PROD")
    monkeypatch.setenv("TRACKER_ORIGIN_GUARD", "1")
    monkeypatch.setenv("TRACKER_CSRF_ENFORCE", "0")
    with TestClient(app, base_url="http://tracker-internal:8000") as client:
        page = client.get("/labs")
        assert page.status_code == 200
        token = client.cookies.get(COOKIE_NAME)
        assert token
        yield client, token


@pytest.mark.parametrize("origin", ("null", "https://tracker.example"))
def test_500_actual_labs_post_requires_valid_signed_token(isolated_app, origin):
    client, token = isolated_app
    response = client.post(
        "/labs",
        headers={
            "Origin": origin,
            "Sec-Fetch-Site": "same-origin",
            HEADER_NAME: token,
        },
        data={"drawn_on": "2026-11-08", "lab_name": "test-only"},
        follow_redirects=False,
    )
    # Empty result list causes normal form validation; no Labs record created.
    assert response.status_code == 200
    assert response.headers["x-tracker-csrf-report"] == "valid"
    assert "Add at least one result" in response.text


@pytest.mark.parametrize("origin,fetch_site,token_mode", (
    ("null", "cross-site", "correct"),
    ("null", "same-site", "correct"),
    ("null", "same-origin", "incorrect"),
    ("null", "same-origin", "missing"),
    ("https://tracker.example", "same-origin", "incorrect"),
    ("http://tracker.example", "same-origin", "correct"),
))
def test_500_actual_labs_post_rejects_invalid_origin_or_csrf(
    isolated_app, origin, fetch_site, token_mode
):
    client, token = isolated_app
    headers = {"Origin": origin, "Sec-Fetch-Site": fetch_site}
    if token_mode != "missing":
        headers[HEADER_NAME] = token if token_mode == "correct" else "tampered"
    response = client.post(
        "/labs", data={"drawn_on": "2026-11-08"},
        headers=headers, follow_redirects=False
    )
    assert response.status_code == 403


def test_500_unrelated_writes_still_reject_origin_mismatch(isolated_app):
    client, token = isolated_app
    response = client.post(
        "/compounds",
        data={"name": ""},
        headers={
            "Origin": "null",
            "Sec-Fetch-Site": "same-origin",
            HEADER_NAME: token,
        },
        follow_redirects=False,
    )
    assert response.status_code == 403
