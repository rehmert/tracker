"""Release 430: DEV-only secondary preview gateway and session isolation."""

import re
import sqlite3

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from app import config, session_auth385 as auth
from app.security import require_auth
from app.secondary_preview430 import COOKIE, preview_app
from app.user_bootstrap426 import initialize_staged_workspace426
from app.user_accounts427 import stage_secondary_account427
from app.user_storage388 import live_storage_for


@pytest.fixture
def browser(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(config, "instance_label", lambda: "DEV")
    monkeypatch.setenv("TRACKER_SECONDARY_PREVIEW430", "1")

    auth.bootstrap("operator", "administrator-secure-password-430")
    (tmp_path / auth.FLAG).write_text("DEV enabled")

    for uid in (2, 3):
        initialize_staged_workspace426(uid, tmp_path)
        stage_secondary_account427(
            uid, f"member-{uid}", f"secondary-password-{uid}-secure-430",
        )

    with sqlite3.connect(tmp_path / "users" / "2" / "tracker.db") as db:
        db.execute("""
            INSERT INTO compounds (name,category,notes,primary_unit)
            VALUES ('private-2','other','','mg')
        """)

    host = FastAPI(dependencies=[Depends(require_auth)])
    host.mount("/secondary", preview_app)

    @host.get("/admin-only")
    def admin_only():
        return {"secret": True}

    with TestClient(host, base_url="https://tracker.test") as client:
        yield client, tmp_path


def form_token(html):
    # HTML attribute separation may be a space, tab or newline.
    match = re.search(
        r'name="csrf_token"\s+value="([^"]+)"',
        html,
    )
    assert match is not None, "CSRF hidden input missing from HTML form"
    return match.group(1)


@pytest.mark.parametrize(
    "html",
    [
        '<input type="hidden" name="csrf_token" value="token">',
        '<input type="hidden" name="csrf_token"\nvalue="token">',
        '<input type="hidden" name="csrf_token"\tvalue="token">',
    ],
)
def test_form_token_parser_accepts_valid_html_whitespace(html):
    assert form_token(html) == "token"


def login(client, username, password):
    page = client.get("/secondary/login")
    assert page.status_code == 200
    return client.post(
        "/secondary/login",
        data={
            "username": username,
            "password": password,
            "csrf_token": form_token(page.text),
        },
        follow_redirects=False,
    )


def test_gateway_denied_without_opt_in(browser, monkeypatch):
    client, _ = browser
    monkeypatch.delenv("TRACKER_SECONDARY_PREVIEW430")

    assert client.get("/secondary/login").status_code == 404
    assert client.get("/secondary/overview").status_code == 404


def test_independent_secondary_http_session_and_private_overview(browser):
    client, _ = browser

    result = login(client, "member-2", "secondary-password-2-secure-430")
    assert result.status_code == 303
    assert result.headers["location"] == "/secondary/overview"
    assert "secure" in result.headers["set-cookie"].lower()
    assert "httponly" in result.headers["set-cookie"].lower()

    token = client.cookies.get(COOKIE)
    assert token
    assert auth.session_user(token) is None
    with pytest.raises(PermissionError):
        live_storage_for(2)

    page = client.get("/secondary/overview")
    assert page.status_code == 200
    assert "Account 2." in page.text
    assert "<th>Compounds</th><td>1</td>" in page.text

    assert client.get(
        "/admin-only", follow_redirects=False,
    ).status_code == 303
    assert client.get(
        "/secondary/overview?user_id=3",
    ).status_code == 400


def test_two_accounts_resolve_only_their_own_data(browser):
    client, _ = browser
    assert login(
        client, "member-2", "secondary-password-2-secure-430",
    ).status_code == 303

    first = client.get("/secondary/overview")
    assert first.status_code == 200
    assert "Account 2." in first.text
    assert "<th>Compounds</th><td>1</td>" in first.text

    assert login(
        client, "member-3", "secondary-password-3-secure-430",
    ).status_code == 303
    second = client.get("/secondary/overview")
    assert second.status_code == 200
    assert "Account 3." in second.text
    assert "<th>Compounds</th><td>0</td>" in second.text
    assert "<th>Compounds</th><td>1</td>" not in second.text


def test_admin_and_invalid_credentials_cannot_sign_in(browser):
    client, _ = browser
    assert login(
        client, "operator", "administrator-secure-password-430",
    ).status_code == 401
    assert login(
        client, "member-2", "bad-password-long-enough",
    ).status_code == 401
    assert not client.cookies.get(COOKIE)


def test_login_csrf_and_cross_site_guard(browser):
    client, _ = browser
    assert client.post(
        "/secondary/login",
        data={
            "username": "member-2",
            "password": "secondary-password-2-secure-430",
        },
    ).status_code == 403

    page = client.get("/secondary/login")
    assert page.status_code == 200
    token = form_token(page.text)
    assert client.post(
        "/secondary/login",
        headers={"Sec-Fetch-Site": "cross-site"},
        data={
            "username": "member-2",
            "password": "secondary-password-2-secure-430",
            "csrf_token": token,
        },
    ).status_code == 403


def test_logout_revokes_secondary_session_only(browser):
    client, root = browser

    assert login(
        client, "member-2", "secondary-password-2-secure-430",
    ).status_code == 303

    page = client.get("/secondary/overview")
    assert page.status_code == 200, (
        f"Overview failed before logout: {page.status_code}"
    )
    assert 'action="/secondary/logout"' in page.text
    csrf_token = form_token(page.text)

    assert client.post(
        "/secondary/logout",
        data={"csrf_token": "forged"},
    ).status_code == 403

    result = client.post(
        "/secondary/logout",
        data={"csrf_token": csrf_token},
        follow_redirects=False,
    )
    assert result.status_code == 303
    assert result.headers["location"] == "/secondary/login"
    assert client.get(
        "/secondary/overview",
        follow_redirects=False,
    ).status_code == 303

    with sqlite3.connect(root / auth.DATABASE) as db:
        assert db.execute("""
            SELECT COUNT(*) FROM tracker_secondary_sessions430
            WHERE user_id=2
        """).fetchone()[0] == 0


def test_workspace_identity_tampering_revokes_access(browser):
    client, root = browser
    assert login(
        client, "member-2", "secondary-password-2-secure-430",
    ).status_code == 303

    with sqlite3.connect(root / "users" / "2" / "tracker.db") as db:
        db.execute("""
            UPDATE tracker_staged_workspace426 SET user_id=3
        """)

    assert client.get(
        "/secondary/overview", follow_redirects=False,
    ).status_code == 303


def test_secondary_sessions_are_separate_from_admin_sessions(browser):
    client, root = browser
    assert login(
        client, "member-2", "secondary-password-2-secure-430",
    ).status_code == 303

    with sqlite3.connect(root / auth.DATABASE) as db:
        assert db.execute("""
            SELECT COUNT(*) FROM sessions WHERE user_id>1
        """).fetchone()[0] == 0
        assert db.execute("""
            SELECT COUNT(*) FROM tracker_secondary_sessions430
            WHERE user_id=2
        """).fetchone()[0] == 1
        assert db.execute("""
            SELECT enabled FROM users WHERE id=2
        """).fetchone() == (0,)


def test_prod_and_disabled_session_mode_never_expose_gateway(
    browser, monkeypatch,
):
    client, root = browser
    monkeypatch.setattr(config, "instance_label", lambda: "PROD")
    assert client.get("/secondary/login").status_code == 404

    monkeypatch.setattr(config, "instance_label", lambda: "DEV")
    (root / auth.FLAG).unlink()
    assert client.get("/secondary/login").status_code == 404


def test_main_mount_explicitly_opt_in():
    from pathlib import Path

    source = Path("app/main.py").read_text()
    assert "if secondary_preview430.preview_enabled():" in source
    assert 'app.mount("/secondary", secondary_preview430.preview_app)' in source


# Release 464: integrated private dashboard.
def test_workspace464_mobile_hub_and_capability_gates(
    browser, monkeypatch
):
    client, _ = browser
    assert login(
        client, "member-2",
        "secondary-password-2-secure-430",
    ).status_code == 303

    page = client.get("/secondary/overview")
    assert page.status_code == 200
    assert "My Workspace" in page.text
    assert "Private Record Counts" in page.text
    assert 'data-workspace-feature="food"' in page.text
    assert 'href="/secondary/food/new"' not in page.text
    assert "Account 2." in page.text
    assert "<th>Compounds</th><td>1</td>" in page.text
    assert 'action="/secondary/logout"' in page.text

    monkeypatch.setenv(
        "TRACKER_SECONDARY_FOOD_WRITES456", "1"
    )
    monkeypatch.setenv(
        "TRACKER_SECONDARY_VITAL_WRITES433", "1"
    )

    enabled = client.get("/secondary/overview")
    assert enabled.status_code == 200
    assert 'href="/secondary/food/new"' in enabled.text
    assert 'href="/secondary/vitals/new"' in enabled.text

    readiness = client.get("/secondary/readiness")
    assert readiness.status_code == 200
    assert 'data-feature="food"' in readiness.text
    assert "Log Food and Water" in readiness.text

    login(
        client, "member-3",
        "secondary-password-3-secure-430",
    )
    third = client.get("/secondary/overview")
    assert third.status_code == 200
    assert "Account 3." in third.text
    assert "<th>Compounds</th><td>0</td>" in third.text
    assert "<th>Compounds</th><td>1</td>" not in third.text


def test_workspace464_lockdown_and_prod(
    browser, monkeypatch
):
    client, _ = browser
    assert login(
        client, "member-2",
        "secondary-password-2-secure-430",
    ).status_code == 303

    monkeypatch.setenv(
        "TRACKER_SECONDARY_LOCKDOWN440", "1"
    )
    assert client.get("/secondary/overview").status_code == 404
    assert client.get("/secondary/readiness").status_code == 404

    monkeypatch.delenv(
        "TRACKER_SECONDARY_LOCKDOWN440"
    )
    monkeypatch.setattr(
        config, "instance_label", lambda: "PROD"
    )
    assert client.get("/secondary/overview").status_code == 404
    assert client.get("/secondary/readiness").status_code == 404


# Release 465: authenticated current-account readiness.
def test_account465_authenticated_private_page(
    browser, monkeypatch
):
    client, _ = browser

    denied = client.get(
        "/secondary/account",
        follow_redirects=False,
    )

    assert denied.status_code == 303
    assert denied.headers["location"] == "/secondary/login"

    result = login(
        client,
        "member-2",
        "secondary-password-2-secure-430",
    )
    assert result.status_code == 303

    first = client.get("/secondary/account")

    assert first.status_code == 200
    assert first.headers["cache-control"] == "no-store"
    assert first.headers["x-content-type-options"] == "nosniff"

    assert "member-2" in first.text
    assert "member-3" not in first.text
    assert "Production Access" in first.text

    assert client.get(
        "/secondary/account?user_id=3"
    ).status_code == 400

    assert client.post(
        "/secondary/account"
    ).status_code == 405

    dashboard = client.get("/secondary/overview")
    assert dashboard.status_code == 200
    assert 'href="/secondary/account"' in dashboard.text

    result = login(
        client,
        "member-3",
        "secondary-password-3-secure-430",
    )
    assert result.status_code == 303

    second = client.get("/secondary/account")

    assert second.status_code == 200
    assert "member-3" in second.text
    assert "member-2" not in second.text

    monkeypatch.setenv(
        "TRACKER_SECONDARY_LOCKDOWN440", "1"
    )

    assert client.get(
        "/secondary/account"
    ).status_code == 404

    monkeypatch.delenv(
        "TRACKER_SECONDARY_LOCKDOWN440"
    )

    monkeypatch.setattr(
        config, "instance_label", lambda: "PROD"
    )

    assert client.get(
        "/secondary/account"
    ).status_code == 404


def test_account465_cross_user_parameter_rejection(browser):
    client, _ = browser

    result = login(
        client,
        "member-2",
        "secondary-password-2-secure-430",
    )
    assert result.status_code == 303

    no_selector_routes = (
        "/secondary/overview",
        "/secondary/vitals",
        "/secondary/doses",
        "/secondary/inventory",
        "/secondary/readiness",
        "/secondary/security",
        "/secondary/account",
    )

    for route in no_selector_routes:
        response = client.get(
            route + "?user_id=3"
        )

        assert response.status_code == 400, (
            route, response.status_code
        )

    for route in (
        "/secondary/food",
        "/secondary/food/week",
        "/secondary/food/week.csv",
    ):
        response = client.get(
            route + "?user_id=3"
        )

        assert response.status_code == 400, (
            route, response.status_code
        )
