"""Release 479: administrator-only secondary provisioning."""
import os
import re
import stat

import pytest
from fastapi.testclient import TestClient

from app import config, session_auth385 as auth
from app.main import app
from app.secondary_provision479 import create_secondary_user479
from app.user_accounts427 import (
    list_staged_accounts427,
    staged_credential_matches427,
)


@pytest.fixture
def browser(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(
        config, "instance_label", lambda: "DEV"
    )
    monkeypatch.setenv(
        "TRACKER_SECONDARY_PREVIEW430", "1"
    )
    monkeypatch.setenv(
        "TRACKER_MULTIUSER_LOGIN473", "1"
    )
    monkeypatch.delenv(
        "TRACKER_SECONDARY_LOCKDOWN440",
        raising=False,
    )

    auth.bootstrap(
        "operator", "administrator-secure-479"
    )
    (tmp_path / auth.FLAG).write_text("enabled")

    with TestClient(
        app, base_url="https://tracker.test"
    ) as client:
        yield client, tmp_path


def csrf_token(html):
    match = re.search(
        r'name="csrf_token"\s+value="([^"]+)"',
        html,
    )
    assert match and match.group(1)
    return match.group(1)


def login(client, username, password):
    response = client.get("/login")
    assert response.status_code == 200

    return client.post(
        "/login",
        data={
            "username": username,
            "password": password,
            "csrf_token": csrf_token(response.text),
            "next": "/",
        },
        follow_redirects=False,
    )


def form(client, username="new-member", password="abc"):
    response = client.get("/account/users")
    assert response.status_code == 200

    return {
        "csrf_token": csrf_token(response.text),
        "username": username,
        "password": password,
        "confirmation": password,
    }


def admin_login(client):
    result = login(
        client,
        "operator",
        "administrator-secure-479",
    )
    assert result.status_code == 303


def test_management_requires_admin(browser):
    client, _ = browser

    denied = client.get(
        "/account/users",
        follow_redirects=False,
    )
    assert denied.status_code == 303

    admin_login(client)

    page = client.get("/account/users")
    assert page.status_code == 200
    assert "Create Secondary User" in page.text


def test_creates_isolated_user_with_short_password(browser):
    client, root = browser
    admin_login(client)

    created = client.post(
        "/account/users",
        data=form(client),
        follow_redirects=False,
    )

    assert created.status_code == 303
    assert created.headers["location"] == (
        "/account/users?created=1"
    )

    accounts = list_staged_accounts427()
    assert len(accounts) == 1
    assert accounts[0]["user_id"] == 2
    assert accounts[0]["username"] == "new-member"

    assert staged_credential_matches427(
        2, "new-member", "abc"
    )

    workspace = root / "users" / "2"
    database = workspace / "tracker.db"

    assert workspace.is_dir()
    assert database.is_file()
    assert workspace.stat().st_uid == os.geteuid()
    assert database.stat().st_uid == os.geteuid()

    assert stat.S_IMODE(
        workspace.stat().st_mode
    ) == 0o700

    assert stat.S_IMODE(
        database.stat().st_mode
    ) == 0o600


def test_duplicate_user_is_rejected(browser):
    client, root = browser
    admin_login(client)

    first = client.post(
        "/account/users",
        data=form(client),
        follow_redirects=False,
    )
    assert first.status_code == 303

    second = client.post(
        "/account/users",
        data=form(client, username="NEW-MEMBER"),
        follow_redirects=False,
    )
    assert second.status_code == 409

    assert len(list_staged_accounts427()) == 1
    assert not (root / "users" / "3").exists()


def test_invalid_csrf_is_rejected(browser):
    client, root = browser
    admin_login(client)

    values = form(client)
    values["csrf_token"] = "forged"

    result = client.post(
        "/account/users",
        data=values,
        follow_redirects=False,
    )
    assert result.status_code == 403
    assert not (root / "users" / "2").exists()


def test_cross_site_write_is_rejected(browser):
    client, root = browser
    admin_login(client)

    result = client.post(
        "/account/users",
        headers={"Sec-Fetch-Site": "cross-site"},
        data=form(client),
        follow_redirects=False,
    )
    assert result.status_code == 403
    assert not (root / "users" / "2").exists()


def test_secondary_cannot_manage_accounts(browser):
    client, root = browser
    admin_login(client)

    created = client.post(
        "/account/users",
        data=form(client),
        follow_redirects=False,
    )
    assert created.status_code == 303

    secondary = login(
        client, "new-member", "abc"
    )
    assert secondary.status_code == 303
    assert secondary.headers["location"] == (
        "/secondary/overview"
    )

    denied = client.get(
        "/account/users",
        follow_redirects=False,
    )
    assert denied.status_code == 303

    write = client.post(
        "/account/users",
        data={
            "csrf_token": "invalid",
            "username": "intruder",
            "password": "abc",
            "confirmation": "abc",
        },
        follow_redirects=False,
    )
    assert write.status_code == 401
    assert not (root / "users" / "3").exists()


def test_password_confirmation_required(browser):
    client, root = browser
    admin_login(client)

    values = form(client)
    values["confirmation"] = "different"

    result = client.post(
        "/account/users",
        data=values,
        follow_redirects=False,
    )
    assert result.status_code == 422
    assert not (root / "users" / "2").exists()


def test_production_management_disabled(browser, monkeypatch):
    client, _ = browser
    admin_login(client)

    monkeypatch.setattr(
        config, "instance_label", lambda: "PROD"
    )

    assert client.get("/account/users").status_code == 404


def test_shared_provisioning_api(browser):
    _, root = browser

    result = create_secondary_user479(
        "api-member", "x", "x"
    )

    assert result["user_id"] == 2
    assert result["username"] == "api-member"
    assert (
        root / "users" / "2" / "tracker.db"
    ).is_file()
