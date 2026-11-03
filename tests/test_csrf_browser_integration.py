"""CSRF cookie rollout and backwards compatibility."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import config
from app.csrf_runtime import (
    COOKIE_NAME,
    load_key,
    prepare_html_cookie,
)
from app.csrf_tokens import verify_pair, verify_token
from app.main import app


@pytest.fixture
def browser(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "AUTH_USER", "")
    monkeypatch.setattr(config, "AUTH_PASS", "")
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)

    with TestClient(app) as client:
        yield client, tmp_path


def test_html_get_issues_signed_cookie(browser):
    client, directory = browser

    response = client.get("/labs")

    assert response.status_code == 200
    assert COOKIE_NAME in response.cookies

    token = response.cookies[COOKIE_NAME]
    secret = load_key(
        directory / ".tracker-csrf-signing-key-v1"
    )

    assert verify_token(token, secret)
    assert verify_pair(token, token, secret)
    assert response.headers[
        "cache-control"
    ] == "private, no-store"


def test_cookie_reused_across_page_requests(browser):
    client, _ = browser

    first = client.get("/labs")
    second = client.get("/vials")

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.cookies[COOKIE_NAME] == client.cookies[
        COOKIE_NAME
    ]
    assert COOKIE_NAME not in second.cookies


def test_cookie_attributes(browser):
    client, _ = browser

    response = client.get("/labs")
    cookies = response.headers["set-cookie"].lower()

    assert "samesite=strict" in cookies
    assert "path=/" in cookies
    assert "domain=" not in cookies


def test_health_and_static_do_not_issue_cookie(browser):
    client, _ = browser

    health = client.get("/healthz")
    static = client.get("/static/app.css")

    assert health.status_code == 200
    assert static.status_code == 200
    assert COOKIE_NAME not in health.cookies
    assert COOKIE_NAME not in static.cookies


def test_key_persists_and_is_private(tmp_path):
    path = tmp_path / "csrf.key"

    first = load_key(path)
    second = load_key(path)

    assert first == second
    assert len(first) == 32
    assert path.stat().st_mode & 0o077 == 0


def test_weak_or_corrupt_key_rejected(tmp_path):
    path = tmp_path / "csrf.key"
    path.write_bytes(b"too-short")
    path.chmod(0o600)

    with pytest.raises(ValueError):
        load_key(path)


def test_insecure_key_permissions_rejected(tmp_path):
    path = tmp_path / "csrf.key"
    path.write_bytes(b"a" * 32)
    path.chmod(0o644)

    with pytest.raises(ValueError):
        load_key(path)


def test_symlink_key_rejected(tmp_path):
    target = tmp_path / "original"
    target.write_bytes(b"b" * 32)
    target.chmod(0o600)

    link = tmp_path / "csrf.key"
    link.symlink_to(target)

    with pytest.raises((ValueError, OSError)):
        load_key(link)


def test_legacy_post_still_reaches_form_validation(browser):
    client, _ = browser

    response = client.post(
        "/compounds",
        data={},
        follow_redirects=False,
    )

    assert response.status_code == 422


def test_browser_script_is_wired(browser):
    client, _ = browser

    response = client.get("/labs")
    assert response.status_code == 200
    assert "tracker-csrf-browser.js" in response.text


def test_browser_script_has_submission_paths():
    source = Path(
        "app/static/js/tracker-csrf-browser.js"
    ).read_text()

    assert "htmx:configRequest" in source
    assert "MutationObserver" in source
    assert "csrf_token" in source
    assert "X-Tracker-CSRF" in source


def test_pk_json_script_sends_header():
    source = Path("app/static/pk.js").read_text()
    assert "window.trackerCsrfToken?.()" in source
    assert "X-Tracker-CSRF" in source
