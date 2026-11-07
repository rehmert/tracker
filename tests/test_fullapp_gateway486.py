"""Release 486: fail-closed private full-app routing authorization."""

import re
import sqlite3

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from app import config, session_auth385 as admin_auth
from app.fullapp_gateway486 import (
    READ_ONLY_PAGES486, authorize_fullapp_route486,
)
from app.secondary_preview430 import (
    COOKIE, _revoke, preview_app,
)
from app.user_accounts427 import stage_secondary_account427
from app.user_bootstrap426 import initialize_staged_workspace426


@pytest.fixture
def gateway(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(config, "instance_label", lambda: "DEV")
    monkeypatch.setenv("TRACKER_SECONDARY_PREVIEW430", "1")
    monkeypatch.setenv("TRACKER_FULLAPP_GATEWAY486", "1")
    monkeypatch.setenv("TRACKER_SECONDARY_LOCKDOWN440", "0")

    admin_auth.bootstrap(
        "admin-486", "admin-credential-486-private-gateway"
    )
    (tmp_path / admin_auth.FLAG).write_text("DEV enabled")
    for uid in (2, 3):
        initialize_staged_workspace426(uid, tmp_path)
        stage_secondary_account427(
            uid, f"member-{uid}",
            f"secondary-password-{uid}-secure-486",
        )

    # Test-only route is deliberately NOT mounted in app.main.
    # The future production gateway implementation remains gated.
    host = FastAPI()

    def plan(request: Request, path: str):
        result = authorize_fullapp_route486(request, path)
        return {
            "user_id": result.user_id,
            "method": result.method,
            "route": result.route,
            "db": result.database.name,
            "root_user_id": result.workspace_root.name,
        }

    host.add_api_route(
        "/secondary/full/{path:path}",
        plan,
        methods=["GET", "POST"],
    )
    host.mount("/secondary", preview_app)

    with TestClient(host, base_url="https://tracker.test") as client:
        yield client, tmp_path


def login(client, user_id):
    initial = client.get("/secondary/login")
    assert initial.status_code == 200
    match = re.search(
        r'name="csrf_token"\s+value="([^"]+)"',
        initial.text,
    )
    assert match
    result = client.post(
        "/secondary/login",
        data={
            "username": f"member-{user_id}",
            "password": f"secondary-password-{user_id}-secure-486",
            "csrf_token": match.group(1),
        },
        follow_redirects=False,
    )
    assert result.status_code == 303
    assert client.cookies.get(COOKIE)


def test_denies_anonymous_request(gateway):
    client, _ = gateway
    assert client.get("/secondary/full/compounds").status_code == 401


def test_server_session_alone_selects_private_database(gateway):
    client, root = gateway
    login(client, 2)
    token2 = client.cookies.get(COOKIE)

    for page in READ_ONLY_PAGES486:
        endpoint = "/secondary/full" + (page if page != "/" else "/")
        response = client.get(endpoint, headers={
            "X-Tracker-User-Id": "3",
            "X-Tracker-Data-Dir": str(root / "users" / "3"),
        })
        assert response.status_code == 200, response.text
        result = response.json()
        assert result["user_id"] == 2
        assert result["root_user_id"] == "2"
        assert result["db"] == "tracker.db"
        assert result["route"] == page
        assert result["method"] == "GET"

    login(client, 3)
    for page in ("/compounds", "/labs", "/food"):
        result = client.get("/secondary/full" + page).json()
        assert result["user_id"] == 3
        assert result["root_user_id"] == "3"

    # The first user session cannot turn into user 3.
    client.cookies.clear()
    client.cookies.set(COOKIE, token2, path="/secondary")
    response = client.get("/secondary/full/compounds")
    assert response.status_code == 200
    assert response.json()["user_id"] == 2


def test_rejects_workspace_selectors_and_unlisted_paths(gateway):
    client, _ = gateway
    login(client, 2)

    for key in ("user_id", "uid", "account_id", "tenant_id",
                "database", "db_path", "data_dir", "workspace_root"):
        response = client.get(
            "/secondary/full/compounds", params={key: "3"}
        )
        assert response.status_code == 400, (key, response.text)

    for path in (
        "/secondary/full/login",
        "/secondary/full/account/users",
        "/secondary/full/secondary/overview",
        "/secondary/full/backups",
        "/secondary/full/../labs",
    ):
        assert client.get(
            path, follow_redirects=False
        ).status_code in (400, 404), path

    assert client.get(
        "/secondary/full/food?day=2026-11-07"
    ).status_code == 200
    assert client.post(
        "/secondary/full/food", data={"user_id": "2"}
    ).status_code == 405


def test_revoked_session_and_lockdown_fail_closed(gateway, monkeypatch):
    client, _ = gateway
    login(client, 2)
    token = client.cookies.get(COOKIE)
    _revoke(token)

    assert client.get("/secondary/full/vitals").status_code == 401

    login(client, 2)
    monkeypatch.setenv("TRACKER_SECONDARY_LOCKDOWN440", "1")
    assert client.get("/secondary/full/vitals").status_code == 404
    monkeypatch.setenv("TRACKER_SECONDARY_LOCKDOWN440", "0")

    monkeypatch.setenv("TRACKER_FULLAPP_GATEWAY486", "0")
    assert client.get("/secondary/full/vitals").status_code == 404


def test_prod_denied_even_when_flag_enabled(gateway, monkeypatch):
    client, _ = gateway
    login(client, 2)
    monkeypatch.setattr(config, "instance_label", lambda: "PROD")
    assert client.get("/secondary/full/compounds").status_code == 404


def test_tampered_private_identity_denied(gateway):
    client, root = gateway
    login(client, 2)

    with sqlite3.connect(root / "users" / "2" / "tracker.db") as db:
        db.execute("""
            UPDATE tracker_staged_workspace426 SET user_id=3
        """)

    # Session validation inspects the staged workspace first. When its
    # identity marker is forged, authentication fails closed as 401;
    # the downstream workspace resolver is never reached.
    response = client.get("/secondary/full/compounds")
    assert response.status_code == 401
    assert "users/2" not in response.text
    assert "tracker.db" not in response.text


def test_no_live_forwarder_or_main_app_mount():
    from pathlib import Path
    source = Path("app/fullapp_gateway486.py").read_text()
    main = Path("app/main.py").read_text()
    assert "authorize_fullapp_route486" in source
    assert "subprocess.Popen(" not in source
    assert "httpx.AsyncClient(" not in source
    assert 'app.mount("/secondary/full"' not in main
    assert 'TRACKER_FULLAPP_GATEWAY486' not in main
