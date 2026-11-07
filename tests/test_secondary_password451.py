"""Release 451 secondary security route contracts."""
from pathlib import Path

from app.secondary_password451 import change_secondary_password451
from app.secondary_preview430 import preview_app


def test_secondary_password_route_registered():
    routes = {r.path: r for r in preview_app.routes}
    assert "/security/password" in routes
    assert routes["/security/password"].methods == {"POST"}


def test_preview_security_page_has_password_rotation_controls():
    source = Path("app/secondary_preview430.py").read_text()
    assert 'action="/secondary/security/password"' in source
    assert 'name="current_password"' in source
    assert 'name="new_password"' in source
    assert 'name="confirm_password"' in source
    assert "delete_cookie" in source


def test_gate_is_restricted_to_dev_preview():
    source = Path("app/main.py").read_text()
    assert '"/secondary/security/password"' in source
    assert "secondary_preview430.preview_enabled()" in source
    assert change_secondary_password451.__module__ == "app.secondary_password451"

import pytest
from app import config
from app.user_accounts427 import staged_credential_matches427
from app.secondary_sessions441 import session_overview441
import hashlib
import re
import sqlite3
import time
from contextlib import ExitStack, closing

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app import session_auth385 as auth
from app.secondary_preview430 import COOKIE, preview_app
from app.user_accounts427 import stage_secondary_account427
from app.user_bootstrap426 import initialize_staged_workspace426



@pytest.fixture
def browsers(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(config, "instance_label", lambda: "DEV")
    monkeypatch.setenv("TRACKER_SECONDARY_PREVIEW430", "1")
    monkeypatch.delenv("TRACKER_SECONDARY_LOCKDOWN440", raising=False)

    auth.bootstrap("operator", "administrator-secure-password-441")
    (tmp_path / auth.FLAG).write_text("DEV enabled")

    for uid in (2, 3):
        initialize_staged_workspace426(uid, tmp_path)
        stage_secondary_account427(
            uid, f"member-{uid}", f"secondary-secure-password-{uid}-441",
        )

    # An administrator session is deliberately present and must survive.
    with closing(auth.connect()) as db:
        db.execute(
            "INSERT INTO sessions(token_hash,user_id,expires_at) VALUES (?,?,?)",
            ("a" * 64, 1, int(time.time()) + 3600),
        )
        db.commit()

    host = FastAPI()
    host.mount("/secondary", preview_app)

    with ExitStack() as stack:
        clients = [
            stack.enter_context(
                TestClient(host, base_url="https://tracker.test")
            )
            for _ in range(3)
        ]
        yield clients, tmp_path


def _csrf(html):
    token = re.search(
        r'name="csrf_token"\s+value="([^"]+)"', html,
    )
    assert token, "CSRF field missing"
    return token.group(1)


def _login(client, uid):
    page = client.get("/secondary/login")
    assert page.status_code == 200
    result = client.post(
        "/secondary/login",
        data={
            "username": f"member-{uid}",
            "password": f"secondary-secure-password-{uid}-441",
            "csrf_token": _csrf(page.text),
        },
        follow_redirects=False,
    )
    assert result.status_code == 303, result.text[:250]
    return client.cookies.get(COOKIE)


def _count(root, uid):
    with sqlite3.connect(root / auth.DATABASE) as db:
        return db.execute("""
            SELECT COUNT(*) FROM tracker_secondary_sessions430
            WHERE user_id=? AND expires_at>?
        """, (uid, int(time.time()))).fetchone()[0]


def _admin_count(root):
    with sqlite3.connect(root / auth.DATABASE) as db:
        return db.execute(
            "SELECT COUNT(*) FROM sessions WHERE user_id=1"
        ).fetchone()[0]


def _private_digests(root):
    return tuple(
        hashlib.sha256(
            (root / "users" / str(uid) / "tracker.db").read_bytes()
        ).hexdigest()
        for uid in (2, 3)
    )


def _login_all(browsers):
    clients, _ = browsers
    first = _login(clients[0], 2)
    second = _login(clients[1], 2)
    third = _login(clients[2], 3)
    assert first != second and second != third
    return first, second, third



# All fixtures and helpers are local to this test module.



def _form(client, before, after, confirm=None):
    page = client.get("/secondary/security")
    assert page.status_code == 200
    return {
        "csrf_token": _csrf(page.text),
        "current_password": before,
        "new_password": after,
        "confirm_password": after if confirm is None else confirm,
    }


def test_own_password_rotation_revokes_only_own_sessions(browsers):
    clients, root = browsers
    first, second, third = _login_all(browsers)
    before = _private_digests(root)
    old = "secondary-secure-password-2-441"
    new = "rotated-secondary-secret-451"
    response = clients[0].post(
        "/secondary/security/password",
        data=_form(clients[0], old, new),
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert response.headers["location"] == "/secondary/login"
    assert (_count(root, 2), _count(root, 3), _admin_count(root)) == (0, 1, 1)
    assert _private_digests(root) == before
    assert not staged_credential_matches427(2, "member-2", old)
    assert staged_credential_matches427(2, "member-2", new)
    assert staged_credential_matches427(
        3, "member-3", "secondary-secure-password-3-441"
    )
    with pytest.raises(PermissionError):
        session_overview441(first)
    with pytest.raises(PermissionError):
        session_overview441(second)
    assert session_overview441(third)["active_sessions"] == 1



@pytest.mark.parametrize("kind", ("wrong", "reused", "empty", "mismatch"))
def test_bad_password_changes_leave_sessions_intact(browsers, kind):
    clients, root = browsers
    _login_all(browsers)
    old = "secondary-secure-password-2-441"
    new = "rotated-secondary-secret-451"
    before = _private_digests(root)
    if kind == "wrong":
        args = ("incorrect-original-secret", new, new)
    elif kind == "reused":
        args = (old, old, old)
    elif kind == "empty":
        args = (old, "", "")
    else:
        args = (old, new, "confirmation-does-not-match")
    result = clients[0].post(
        "/secondary/security/password",
        data=_form(clients[0], args[0], args[1], args[2]),
        follow_redirects=False,
    )
    assert result.status_code == 422
    assert (_count(root, 2), _count(root, 3), _admin_count(root)) == (2, 1, 1)
    assert _private_digests(root) == before
    assert staged_credential_matches427(2, "member-2", old)


def test_csrf_unexpected_fields_and_cross_site_rejected(browsers):
    clients, root = browsers
    _login_all(browsers)
    old = "secondary-secure-password-2-441"
    new = "rotated-secondary-secret-451"
    valid = _form(clients[0], old, new)

    result = clients[0].post(
        "/secondary/security/password",
        data={**valid, "user_id": "3"},
    )
    assert result.status_code == 422
    result = clients[0].post(
        "/secondary/security/password",
        data={**valid, "csrf_token": "not-valid"},
    )
    assert result.status_code == 403
    result = clients[0].post(
        "/secondary/security/password",
        data=valid,
        headers={"Sec-Fetch-Site": "cross-site"},
    )
    assert result.status_code == 403
    result = clients[0].post(
        "/secondary/security/password?user_id=3",
        data=valid,
    )
    assert result.status_code == 400
    assert (_count(root, 2), _count(root, 3), _admin_count(root)) == (2, 1, 1)
    assert staged_credential_matches427(2, "member-2", old)


def test_password_gateway_stays_disabled_when_locked_or_prod(browsers, monkeypatch):
    clients, root = browsers
    _login_all(browsers)
    form = _form(
        clients[0], "secondary-secure-password-2-441",
        "rotated-secondary-secret-451",
    )
    monkeypatch.setenv("TRACKER_SECONDARY_LOCKDOWN440", "1")
    assert clients[0].post(
        "/secondary/security/password", data=form,
    ).status_code == 404
    monkeypatch.delenv("TRACKER_SECONDARY_LOCKDOWN440", raising=False)
    monkeypatch.setattr(config, "instance_label", lambda: "PROD")
    assert clients[0].post(
        "/secondary/security/password", data=form,
    ).status_code == 404


def test_current_password_attempt_limit_prevents_repeated_guesses(browsers):
    clients, root = browsers
    _login_all(browsers)
    for _ in range(8):
        result = clients[0].post(
            "/secondary/security/password",
            data=_form(
                clients[0],
                "incorrect-current-password-451",
                "rotated-secondary-secret-451",
            ),
            follow_redirects=False,
        )
        assert result.status_code == 422
    result = clients[0].post(
        "/secondary/security/password",
        data=_form(
            clients[0],
            "secondary-secure-password-2-441",
            "rotated-secondary-secret-451",
        ),
        follow_redirects=False,
    )
    assert result.status_code == 422
    assert (_count(root, 2), _count(root, 3), _admin_count(root)) == (2, 1, 1)


def test_missing_session_and_duplicate_fields_are_denied(browsers):
    clients, root = browsers
    no_session = clients[0].post(
        "/secondary/security/password", data={},
    )
    assert no_session.status_code == 401
    _login_all(browsers)
    form = _form(
        clients[0], "secondary-secure-password-2-441",
        "rotated-secondary-secret-451",
    )
    # URL-encoded duplicate form fields must not be accepted.
    from urllib.parse import urlencode
    fields = list(form.items())
    fields.append(("new_password", "alternative-replacement-451"))
    result = clients[0].post(
        "/secondary/security/password",
        content=urlencode(fields),
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert result.status_code == 422
    assert _admin_count(root) == 1
    assert _count(root, 2) == 2


def test_security_page_never_renders_existing_credentials(browsers):
    clients, root = browsers
    _login_all(browsers)
    page = clients[0].get("/secondary/security")
    assert page.status_code == 200
    assert "Change My Password" in page.text
    assert 'action="/secondary/security/password"' in page.text
    assert "Change Password and Sign Out All Devices" in page.text
    assert "secondary-secure-password-2-441" not in page.text
    assert str(root) not in page.text
    assert page.headers["cache-control"] == "no-store"


def test_release451_has_no_implicit_cross_module_test_imports():
    import ast
    tree = ast.parse(Path(__file__).read_text())
    dependencies = [
        node.module for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module
    ]
    assert all(not name.startswith("test_secondary_") for name in dependencies)
    assert all(not name.startswith("tests.") for name in dependencies)



def test_short_secondary_password_rotation(browsers):
    clients, _ = browsers
    old = "secondary-secure-password-2-441"

    token = _login(clients[0], 2)
    assert token

    result = clients[0].post(
        "/secondary/security/password",
        data=_form(clients[0], old, "abc"),
        follow_redirects=False,
    )

    assert result.status_code == 303
    assert not staged_credential_matches427(
        2, "member-2", old
    )
    assert staged_credential_matches427(
        2, "member-2", "abc"
    )

    # Existing session must have been revoked.
    with pytest.raises(PermissionError):
        session_overview441(token)
