"""Release 432: authenticated read-only vitals and doses per private user."""

import re
import sqlite3
import subprocess
import sys

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app import config, session_auth385 as auth
from app.secondary_preview430 import preview_app
from app.user_bootstrap426 import initialize_staged_workspace426
from app.user_accounts427 import stage_secondary_account427
from app.worker_recent432 import read_recent432, parse_request432
from app.worker_scope428 import SOURCE_ROOT, worker_environment428


@pytest.fixture
def browser(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(config, "instance_label", lambda: "DEV")
    monkeypatch.setenv("TRACKER_SECONDARY_PREVIEW430", "1")

    auth.bootstrap("operator", "administrator-very-secure-pass432")
    (tmp_path / auth.FLAG).write_text("DEV enabled")

    for uid in (2, 3):
        initialize_staged_workspace426(uid, tmp_path)
        stage_secondary_account427(
            uid, f"member-{uid}", f"secondary-secure-pass-{uid}-432",
        )

        path = tmp_path / "users" / str(uid) / "tracker.db"
        with sqlite3.connect(path) as db:
            db.execute("""
                INSERT INTO vital_readings
                    (measured_at,weight_kg,systolic,diastolic,pulse_bpm,context,notes)
                VALUES (?,?,?,?,?,?,?)
            """, (
                f"2026-11-0{uid} 08:00:00",
                100.0 + uid, 110 + uid, 70 + uid, 65 + uid,
                f"PRIVATE-{uid}", "private note not returned",
            ))

            name = '<img src=x onerror="alert(1)">' if uid == 2 else "SAFE-THREE"
            db.execute("""
                INSERT INTO compounds(name,category,notes,primary_unit)
                VALUES (?,?,?,?)
            """, (name, "other", "", "mg"))
            cid = db.execute(
                "SELECT id FROM compounds WHERE name=?", (name,)
            ).fetchone()[0]

            db.execute("""
                INSERT INTO vials
                    (compound_id,label,lot,cap_color,kit_ref,form,content_value,
                     content_unit,status,use_coa_content,unit_price_cents,notes,
                     storage_notes)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, (
                cid, "test", "", "", "", "lyophilized", 10, "mg",
                "in_use", 0, 0, "", "",
            ))
            vid = db.execute(
                "SELECT id FROM vials WHERE compound_id=?", (cid,)
            ).fetchone()[0]
            db.execute("""
                INSERT INTO dose_logs
                    (vial_id,taken_at,entered_value,entered_unit,
                     amount_base,kind,site,notes)
                VALUES (?,?,?,?,?,?,?,?)
            """, (
                vid, f"2026-11-0{uid} 09:00:00",
                uid, "mg", 1000 * uid,
                "dose", f"PRIVATE-SITE-{uid}", "secret notes excluded",
            ))

    host = FastAPI()
    host.mount("/secondary", preview_app)

    with TestClient(
        host, base_url="https://tracker.test"
    ) as client:
        yield client, tmp_path


def login(client, uid):
    page = client.get("/secondary/login")
    assert page.status_code == 200
    match = re.search(
        r'name="csrf_token"\s+value="([^"]+)"', page.text
    )
    assert match
    result = client.post(
        "/secondary/login",
        data={
            "username": f"member-{uid}",
            "password": f"secondary-secure-pass-{uid}-432",
            "csrf_token": match.group(1),
        },
        follow_redirects=False,
    )
    assert result.status_code == 303


def test_private_vital_and_dose_rows_do_not_cross_accounts(browser):
    client, _ = browser

    login(client, 2)
    first_vitals = client.get("/secondary/vitals")
    first_doses = client.get("/secondary/doses")

    assert first_vitals.status_code == 200
    assert first_doses.status_code == 200
    assert "PRIVATE-2" in first_vitals.text
    assert "PRIVATE-3" not in first_vitals.text
    assert "PRIVATE-SITE-2" in first_doses.text
    assert "PRIVATE-SITE-3" not in first_doses.text
    assert "&lt;img" in first_doses.text
    assert '<img src=x onerror=' not in first_doses.text
    assert "secret notes excluded" not in first_doses.text
    assert first_doses.headers["cache-control"] == "no-store"

    login(client, 3)
    second_vitals = client.get("/secondary/vitals")
    second_doses = client.get("/secondary/doses")

    assert second_vitals.status_code == 200
    assert second_doses.status_code == 200
    assert "PRIVATE-3" in second_vitals.text
    assert "PRIVATE-2" not in second_vitals.text
    assert "PRIVATE-SITE-3" in second_doses.text
    assert "PRIVATE-SITE-2" not in second_doses.text
    assert "SAFE-THREE" in second_doses.text
    assert "&lt;img" not in second_doses.text


def test_no_user_id_or_sql_query_parameters(browser):
    client, _ = browser
    login(client, 2)

    for path in (
        "/secondary/vitals?user_id=3",
        "/secondary/doses?database=/tmp/other.db",
        "/secondary/doses?sql=SELECT%201",
    ):
        assert client.get(path).status_code == 400

    assert client.post("/secondary/vitals").status_code == 405
    assert client.post("/secondary/doses").status_code == 405


def test_unauthenticated_and_admin_cookie_cannot_read(browser):
    client, _ = browser

    for path in ("/secondary/vitals", "/secondary/doses"):
        result = client.get(path, follow_redirects=False)
        assert result.status_code == 303
        assert result.headers["location"] == "/secondary/login"


def test_identity_tampering_fails_closed(browser):
    client, root = browser
    login(client, 2)

    with sqlite3.connect(root / "users" / "2" / "tracker.db") as db:
        db.execute(
            "UPDATE tracker_staged_workspace426 SET user_id=3"
        )

    result = client.get(
        "/secondary/vitals", follow_redirects=False,
    )
    assert result.status_code == 303


@pytest.mark.parametrize("payload", [
    b'',
    b'{"action":"vitals","user_id":3}',
    b'{"action":"doses","sql":"SELECT * FROM users"}',
    b'{"action":"all"}',
    b'{"action":"vitals","action":"doses"}',
    b'[]',
    b'x' * 257,
])
def test_private_worker_request_allowlist_rejects_other_inputs(payload):
    with pytest.raises(ValueError):
        parse_request432(payload)


def test_parent_read_is_fixed_to_private_user(browser):
    _, root = browser
    first = read_recent432(2, "vitals", root)
    second = read_recent432(3, "doses", root)

    assert first["user_id"] == 2
    assert second["user_id"] == 3
    assert first["items"][0]["context"] == "PRIVATE-2"
    assert second["items"][0]["site"] == "PRIVATE-SITE-3"

    with pytest.raises(PermissionError):
        read_recent432(1, "vitals", root)
    with pytest.raises(ValueError):
        read_recent432(2, "query", root)


def test_child_rejects_forged_workspace_path(browser):
    _, root = browser
    env = worker_environment428(2, root)
    env["TRACKER_DATA_DIR"] = str(root / "users" / "3")

    result = subprocess.run(
        [sys.executable, "-m", "app.worker_recent432"],
        input='{"action":"vitals"}',
        env=env, cwd=SOURCE_ROOT,
        text=True, capture_output=True,
        timeout=45,
    )
    assert result.returncode != 0
    assert not result.stdout.strip()
    assert "Worker data directory does not match identity" in result.stderr


def test_opt_in_and_prod_restrictions_remain_active(browser, monkeypatch):
    client, _ = browser
    monkeypatch.delenv("TRACKER_SECONDARY_PREVIEW430")
    assert client.get("/secondary/vitals").status_code == 404
    monkeypatch.setenv("TRACKER_SECONDARY_PREVIEW430", "1")
    monkeypatch.setattr(config, "instance_label", lambda: "PROD")
    assert client.get("/secondary/doses").status_code == 200


def test_recent_orm469_worker_bypassed_and_users_isolated(
    browser, monkeypatch
):
    from app import secondary_preview430
    from app.secondary_preview430 import COOKIE

    client, root = browser

    def forbidden_worker(*args, **kwargs):
        raise AssertionError(
            "Legacy worker called by migrated route"
        )

    monkeypatch.setattr(
        secondary_preview430,
        "read_recent432",
        forbidden_worker,
    )

    login(client, 2)

    first_vitals = client.get("/secondary/vitals")
    first_doses = client.get("/secondary/doses")

    assert first_vitals.status_code == 200
    assert first_doses.status_code == 200

    assert "PRIVATE-2" in first_vitals.text
    assert "PRIVATE-3" not in first_vitals.text
    assert "PRIVATE-SITE-2" in first_doses.text
    assert "PRIVATE-SITE-3" not in first_doses.text

    assert "&lt;img" in first_doses.text
    assert '<img src=x onerror=' not in first_doses.text

    assert "secret notes excluded" not in first_doses.text
    assert "private note not returned" not in first_vitals.text

    first_cookie = client.cookies.get(COOKIE)
    assert first_cookie

    login(client, 3)

    second_vitals = client.get("/secondary/vitals")
    second_doses = client.get("/secondary/doses")

    assert second_vitals.status_code == 200
    assert second_doses.status_code == 200

    assert "PRIVATE-3" in second_vitals.text
    assert "PRIVATE-2" not in second_vitals.text

    assert "PRIVATE-SITE-3" in second_doses.text
    assert "PRIVATE-SITE-2" not in second_doses.text

    # A previously issued account-2 cookie can never
    # choose account-3's database or reuse its identity.
    client.cookies.set(COOKIE, first_cookie)
    restored = client.get("/secondary/vitals")

    assert restored.status_code == 200
    assert "PRIVATE-2" in restored.text
    assert "PRIVATE-3" not in restored.text

    client.cookies.delete(COOKIE)

    assert client.get(
        "/secondary/vitals",
        follow_redirects=False,
    ).status_code == 303


def test_recent_orm469_fail_closed_after_revocation(
    browser
):
    from app.secondary_preview430 import COOKIE, _revoke

    client, _ = browser
    login(client, 2)

    token = client.cookies.get(COOKIE)
    assert token

    assert client.get(
        "/secondary/doses"
    ).status_code == 200

    _revoke(token)

    for route in (
        "/secondary/vitals",
        "/secondary/doses",
    ):
        response = client.get(
            route, follow_redirects=False
        )
        assert response.status_code == 303
        assert (
            response.headers["location"]
            == "/secondary/login"
        )
