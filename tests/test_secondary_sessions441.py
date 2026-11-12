"""Release 441: private secondary-session controls and recovery warnings."""

import hashlib
import re
import sqlite3
import time
from contextlib import ExitStack, closing

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app import config, session_auth385 as auth
from app.secondary_preview430 import COOKIE, preview_app
from app.secondary_sessions441 import (
    revoke_other_sessions441, session_overview441,
)
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


def test_revoke_other_devices_only_for_authenticated_secondary_user(browsers):
    clients, root = browsers
    first, second, third = _login_all(browsers)
    assert (_count(root, 2), _count(root, 3), _admin_count(root)) == (2, 1, 1)
    private_before = _private_digests(root)

    before = clients[0].get("/secondary/security")
    assert before.status_code == 200
    assert before.headers["cache-control"] == "no-store"
    assert "2 active session(s)" in before.text
    assert "1 other active session(s)" in before.text
    assert "Current session expires" in before.text
    assert first not in before.text and second not in before.text
    assert "token_hash" not in before.text
    assert str(root) not in before.text

    post = clients[0].post(
        "/secondary/security/revoke-others",
        data={"csrf_token": _csrf(before.text)},
        follow_redirects=False,
    )
    assert post.status_code == 303
    assert post.headers["location"] == "/secondary/security"
    assert (_count(root, 2), _count(root, 3), _admin_count(root)) == (1, 1, 1)

    assert clients[0].get("/secondary/security").status_code == 200
    assert clients[1].get(
        "/secondary/security", follow_redirects=False,
    ).status_code == 303
    assert clients[2].get("/secondary/security").status_code == 200
    assert _private_digests(root) == private_before

    status = session_overview441(first)
    assert status["active_sessions"] == 1
    assert status["other_sessions"] == 0
    with pytest.raises(PermissionError):
        session_overview441(second)
    assert session_overview441(third)["active_sessions"] == 1


def test_user_three_cannot_revoke_user_two_sessions(browsers):
    clients, root = browsers
    _login_all(browsers)
    form = clients[2].get("/secondary/security")
    assert form.status_code == 200
    assert "1 active session(s)" in form.text
    assert clients[2].post(
        "/secondary/security/revoke-others",
        data={"csrf_token": _csrf(form.text)},
        follow_redirects=False,
    ).status_code == 303

    assert (_count(root, 2), _count(root, 3), _admin_count(root)) == (2, 1, 1)


def test_csrf_unknown_fields_and_query_params_fail_without_revoke(browsers):
    clients, root = browsers
    _login_all(browsers)

    form = clients[0].get("/secondary/security")
    token = _csrf(form.text)
    assert clients[0].post(
        "/secondary/security/revoke-others",
        data={"csrf_token": "invalid"},
    ).status_code == 403
    assert clients[0].post(
        "/secondary/security/revoke-others",
        data={"csrf_token": token},
        headers={"Sec-Fetch-Site": "cross-site"},
    ).status_code == 403

    for data in (
        {"csrf_token": token, "user_id": "3"},
        {"csrf_token": token, "database": "/opt/tracker/data/tracker.db"},
        {"csrf_token": token, "session_hash": "a" * 64},
        {},
    ):
        response = clients[0].post(
            "/secondary/security/revoke-others", data=data,
        )
        assert response.status_code in (403, 422)

    assert clients[0].post(
        "/secondary/security/revoke-others?user_id=3",
        data={"csrf_token": token},
    ).status_code == 400
    assert clients[0].get(
        "/secondary/security?user_id=3"
    ).status_code == 400
    assert (_count(root, 2), _count(root, 3), _admin_count(root)) == (2, 1, 1)


def test_no_session_or_revoked_session_cannot_mutate(browsers):
    clients, root = browsers
    no_session = clients[0]
    assert no_session.get(
        "/secondary/security", follow_redirects=False,
    ).status_code == 303
    assert no_session.post(
        "/secondary/security/revoke-others", data={},
    ).status_code == 401

    first, second, _ = _login_all(browsers)
    revoke_other_sessions441(first)
    assert _count(root, 2) == 1
    with pytest.raises(PermissionError):
        revoke_other_sessions441(second)
    assert _count(root, 2) == 1

    page = clients[0].get("/secondary/overview")
    assert page.status_code == 200
    signed_out = clients[0].post(
        "/secondary/logout",
        data={"csrf_token": _csrf(page.text)},
        follow_redirects=False,
    )
    assert signed_out.status_code == 303
    with pytest.raises(PermissionError):
        session_overview441(first)
    assert _count(root, 2) == 0


def test_recovery_warning_is_explicit_and_credentials_not_exposed(browsers):
    clients, root = browsers
    _login(clients[0], 2)
    readiness = clients[0].get("/secondary/readiness")
    assert readiness.status_code == 200
    assert "Recovery Coverage" in readiness.text
    assert "does not include staged secondary" in readiness.text
    assert "tracker-auth.sqlite3" in readiness.text
    assert "backup and restore coverage is not yet available" in readiness.text
    assert "Session Security" in readiness.text
    assert "secondary-secure-password-2-441" not in readiness.text
    assert str(root) not in readiness.text
    assert 'href="/secondary/security"' in clients[0].get(
        "/secondary/overview"
    ).text
    assert _admin_count(root) == 1


def test_prod_disabled_preview_and_lockdown_denial(browsers, monkeypatch):
    clients, root = browsers
    _login(clients[0], 2)
    page = clients[0].get("/secondary/security")
    assert page.status_code == 200
    token = _csrf(page.text)

    monkeypatch.setenv("TRACKER_SECONDARY_LOCKDOWN440", "1")
    assert clients[0].get("/secondary/security").status_code == 404
    assert clients[0].post(
        "/secondary/security/revoke-others",
        data={"csrf_token": token},
    ).status_code == 404
    assert _admin_count(root) == 1

    monkeypatch.delenv("TRACKER_SECONDARY_LOCKDOWN440", raising=False)
    monkeypatch.setattr(config, "instance_label", lambda: "PROD")
    assert clients[0].get("/secondary/security").status_code == 200
    assert clients[0].post(
        "/secondary/security/revoke-others",
        data={"csrf_token": token},
    ).status_code == 403

    monkeypatch.setattr(config, "instance_label", lambda: "DEV")
    monkeypatch.delenv("TRACKER_SECONDARY_PREVIEW430", raising=False)
    assert clients[0].get("/secondary/security").status_code == 404


def test_session_helper_rejects_admin_or_bad_tokens(browsers):
    clients, _ = browsers
    _login(clients[0], 2)
    for token in ("", "bad", None, "a" * 60):
        with pytest.raises(PermissionError):
            session_overview441(token)
        with pytest.raises(PermissionError):
            revoke_other_sessions441(token)


def test_source_exempts_only_secondary_security_posts_with_preview_gate():
    """Release 451: both security POST routes are gated, no arbitrary routes."""
    import ast
    from pathlib import Path

    source = Path("app/main.py").read_text()
    tree = ast.parse(source)
    assignments = [
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Assign)
        and any(
            isinstance(target, ast.Name)
            and target.id == "secondary_form_post433"
            for target in node.targets
        )
    ]
    assert len(assignments) == 1
    gate = assignments[0]
    gate_source = ast.unparse(gate)
    assert "secondary_preview430.preview_enabled()" in gate_source
    assert "request.method.upper() == 'POST'" in gate_source

    # The explicit exception must contain these two routes, and no
    # additional unreviewed secondary security routes.
    security_routes = []
    for node in ast.walk(gate):
        if (
            isinstance(node, ast.Compare)
            and ast.unparse(node.left) == "request.url.path"
            and len(node.ops) == 1
            and isinstance(node.ops[0], ast.In)
            and len(node.comparators) == 1
            and isinstance(node.comparators[0], ast.Tuple)
        ):
            security_routes.extend(
                value.value
                for value in node.comparators[0].elts
                if isinstance(value, ast.Constant)
                and isinstance(value.value, str)
                and value.value.startswith("/secondary/security/")
            )

    assert security_routes == [
        "/secondary/security/revoke-others",
        "/secondary/security/password",
    ]
    assert "and not secondary_form_post433" in source


# Release 577: independent secondary-session signed CSRF behavior when the
# global strict setting is on. This is an isolated TestClient with disposable
# account state, not a live secondary browser acceptance claim.
def test_577_secondary_session_signed_revoke_under_strict_flag(
    browsers, monkeypatch,
):
    monkeypatch.setenv("TRACKER_CSRF_ENFORCE", "1")
    clients, root = browsers
    _login_all(browsers)
    assert (_count(root, 2), _count(root, 3)) == (2, 1)
    page = clients[0].get("/secondary/security")
    assert page.status_code == 200
    token = _csrf(page.text)

    for data, headers in (
        ({}, {}),
        ({"csrf_token": "forged"}, {}),
        ({"csrf_token": token}, {
            "Origin": "https://attacker.invalid",
            "Sec-Fetch-Site": "cross-site",
        }),
    ):
        rejected = clients[0].post(
            "/secondary/security/revoke-others",
            data=data, headers=headers, follow_redirects=False,
        )
        assert rejected.status_code in (403, 422)
        assert (_count(root, 2), _count(root, 3)) == (2, 1)

    accepted = clients[0].post(
        "/secondary/security/revoke-others",
        data={"csrf_token": token}, follow_redirects=False,
    )
    assert accepted.status_code == 303
    assert (_count(root, 2), _count(root, 3), _admin_count(root)) == (1, 1, 1)
