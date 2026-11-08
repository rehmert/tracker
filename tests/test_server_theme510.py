"""Release 510: server-managed theme uses persistent data, no app reinstall.

The app/test DB is already isolated by tests/conftest.py.
"""
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app import config
from app.routers import theme510


@pytest.fixture()
def client():
    with TestClient(app, follow_redirects=False) as tc:
        yield tc


def test_theme_is_the_last_global_stylesheet_and_shared_with_mobile():
    base = (config.BASE_DIR / "templates" / "base.html").read_text()
    assert base.count('href="/ui/theme.css"') == 1
    assert base.index('tracker-mobile-shell507.css') < base.index('href="/ui/theme.css"')
    assert base.index('href="/ui/theme.css"') < base.index("</head>")
    assert 'tracker-theme.css' not in base
    assert 'href="/static/tracker-dev.webmanifest' in base or "/static/tracker-dev.webmanifest" in base
    mobile = (config.BASE_DIR / "static" / "css" / "tracker-mobile-daily509.css").read_text()
    assert 'background:var(--teal,#1265ad)' in mobile
    assert 'color:var(--teal-ink,#fff)' in mobile
    assert 'outline:3px solid var(--tracker-brand-blue,#1686df)' in mobile
    assert 'tracker-mobile-daily509.css?v=510' in (config.BASE_DIR / 'templates' / 'mobile_today509.html').read_text()


def test_missing_custom_theme_uses_blue_light_and_dark_defaults(client, tmp_path, monkeypatch):
    monkeypatch.setattr(theme510, "THEME_FILE", tmp_path / "not-created.css")
    response = client.get("/ui/theme.css")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/css")
    assert response.headers["cache-control"] == "private, no-store"
    assert response.headers["x-tracker-theme-source"] == "default"
    assert "--teal: #1265ad" in response.text
    assert "--teal: #79b8f7" in response.text
    assert ":root[data-theme=\"dark\"]" in response.text


def test_theme_changes_appear_on_next_request_without_restart(client, tmp_path, monkeypatch):
    override = tmp_path / "tracker-theme.css"
    monkeypatch.setattr(theme510, "THEME_FILE", override)
    override.write_text(":root { --teal: #1d4ed8; }\n")
    first = client.get("/ui/theme.css")
    assert first.status_code == 200
    assert first.headers["x-tracker-theme-source"] == "override"
    assert "--teal: #1d4ed8" in first.text

    updated = tmp_path / "new-theme.css"
    updated.write_text(":root { --teal: #1e40af; }\n")
    updated.replace(override)
    second = client.get("/ui/theme.css")
    assert second.status_code == 200
    assert "--teal: #1e40af" in second.text
    assert "--teal: #1d4ed8" not in second.text
    assert second.headers["cache-control"] == "private, no-store"


def test_custom_theme_has_no_path_parameter_or_post_endpoint(client):
    assert client.get("/ui/theme.css?path=/etc/passwd").status_code == 200
    assert client.post("/ui/theme.css", data={"css": "* {display:none}"}).status_code == 405


def test_unsafe_or_oversized_override_falls_back_safely(client, tmp_path, monkeypatch):
    target = tmp_path / "tracker-theme.css"
    monkeypatch.setattr(theme510, "THEME_FILE", target)
    target.write_bytes(b"\xff")
    assert client.get("/ui/theme.css").headers["x-tracker-theme-source"] == "default"
    target.write_bytes(b" " * (theme510.MAX_THEME_BYTES + 1))
    assert client.get("/ui/theme.css").headers["x-tracker-theme-source"] == "default"
    target.unlink()
    try:
        target.symlink_to(config.BASE_DIR / "templates" / "base.html")
    except (OSError, NotImplementedError):
        pytest.skip("Symlinks not supported on this platform")
    result = client.get("/ui/theme.css")
    assert result.status_code == 200
    assert result.headers["x-tracker-theme-source"] == "default"


def test_user_selected_appearance_is_unchanged():
    javascript = (config.BASE_DIR / "static" / "theme.js").read_text()
    assert "tracker-theme" in javascript
    assert "localStorage" in javascript
    assert "dataset.theme" in javascript
    css = theme510.DEFAULT_FILE.read_text()
    assert ':root[data-theme="light"]' in css
    assert ':root[data-theme="dark"]' in css


def test_authenticated_css_is_private_and_rejects_invalid_credentials(
    client, tmp_path, monkeypatch
):
    """Server-managed CSS must honor the global authentication dependency."""
    import base64
    from app import session_auth385

    monkeypatch.setattr(session_auth385, "enabled", lambda: False)
    monkeypatch.setattr(config, "AUTH_USER", "operator")
    monkeypatch.setattr(config, "AUTH_PASS", "secret")
    monkeypatch.setattr(theme510, "THEME_FILE", tmp_path / "missing.css")

    missing = client.get("/ui/theme.css", follow_redirects=False)
    assert missing.status_code == 401
    assert missing.headers["cache-control"] == "private, no-store"

    bad = base64.b64encode(b"operator:wrong").decode("ascii")
    assert client.get(
        "/ui/theme.css",
        headers={"Authorization": "Basic " + bad},
        follow_redirects=False,
    ).status_code == 401

    good = base64.b64encode(b"operator:secret").decode("ascii")
    response = client.get(
        "/ui/theme.css",
        headers={"Authorization": "Basic " + good},
        follow_redirects=False,
    )
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/css")
    assert response.headers["cache-control"] == "private, no-store"
    assert response.headers["vary"] == "Cookie, Authorization"
    assert response.headers["x-tracker-theme-source"] == "default"
    assert "--tracker-brand-blue" in response.text
