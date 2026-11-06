"""Release 434: private, inventory-safe, DEV-only secondary dose logging."""

import re
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app import config, session_auth385 as auth
from app.secondary_preview430 import preview_app
from app.user_bootstrap426 import initialize_staged_workspace426
from app.user_accounts427 import stage_secondary_account427
from app.worker_dose_write434 import (
    parse_request434, request_dose434, validate_dose434,
)


@pytest.fixture
def browser(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(config, "instance_label", lambda: "DEV")
    monkeypatch.setenv("TRACKER_SECONDARY_PREVIEW430", "1")
    monkeypatch.setenv("TRACKER_SECONDARY_DOSE_WRITES434", "1")

    auth.bootstrap("operator", "administrator-secure-password-434")
    (tmp_path / auth.FLAG).write_text("DEV enabled")

    for uid in (2, 3):
        initialize_staged_workspace426(uid, tmp_path)
        stage_secondary_account427(
            uid, f"member-{uid}", f"secondary-secure-password-{uid}-434",
        )
        with sqlite3.connect(tmp_path / "users" / str(uid) / "tracker.db") as db:
            name = "PRIVATE-COMPOUND-2" if uid == 2 else "<img src=x onerror=alert(1)>"
            db.execute("""
                INSERT INTO compounds(name,category,notes,primary_unit)
                VALUES (?, 'other', '', 'mg')
            """, (name,))
            compound_id = db.execute(
                "SELECT id FROM compounds WHERE name=?", (name,)
            ).fetchone()[0]
            db.execute("""
                INSERT INTO vials
                    (compound_id,label,lot,cap_color,kit_ref,form,content_value,
                     content_unit,status,use_coa_content,unit_price_cents,notes,
                     storage_notes)
                VALUES (?, ?, '', '', '', 'lyophilized', 10, 'mg',
                        'sealed', 0, 0, '', '')
            """, (compound_id, f"PRIVATE-VIAL-{uid}"))

    host = FastAPI()
    host.mount("/secondary", preview_app)
    with TestClient(host, base_url="https://tracker.test") as client:
        yield client, tmp_path


def _field(html, key):
    match = re.search(
        rf'name="{re.escape(key)}"\s+value="([^"]+)"',
        html,
    )
    assert match is not None, f"Expected hidden field {key}"
    return match.group(1)


def _login(client, uid):
    page = client.get("/secondary/login")
    assert page.status_code == 200
    response = client.post(
        "/secondary/login",
        data={
            "username": f"member-{uid}",
            "password": f"secondary-secure-password-{uid}-434",
            "csrf_token": _field(page.text, "csrf_token"),
        },
        follow_redirects=False,
    )
    assert response.status_code == 303


def _dose_form(client):
    page = client.get("/secondary/doses/new")
    assert page.status_code == 200, page.text[:250]
    assert 'action="/secondary/doses/new"' in page.text
    return {
        "csrf_token": _field(page.text, "csrf_token"),
        "submission_token": _field(page.text, "submission_token"),
        "vial_id": "1",
        "taken_at": datetime.now().strftime("%Y-%m-%dT%H:%M"),
        "amount": "3",
        "unit": "mg",
        "site": "Abdomen lower left",
        "notes": "PRIVATE-DOSE-NOTES",
    }


def _state(root, uid):
    database = root / "users" / str(uid) / "tracker.db"
    with sqlite3.connect(database) as conn:
        doses = conn.execute("""
            SELECT vial_id,entered_value,entered_unit,amount_base,kind,site
            FROM dose_logs ORDER BY id
        """).fetchall()
        vials = conn.execute(
            "SELECT status FROM vials ORDER BY id"
        ).fetchall()
        tokens = conn.execute("""
            SELECT COUNT(*) FROM inventory_submissions
            WHERE operation='secondary_dose_create434'
        """).fetchone()[0]
    return doses, vials, tokens


def test_authenticated_dose_write_is_private_and_decrements_available(browser):
    client, root = browser
    _login(client, 2)

    page = client.get("/secondary/doses/new")
    assert page.status_code == 200
    assert "PRIVATE-VIAL-2" in page.text
    assert "<img" not in page.text
    data = _dose_form(client)

    result = client.post(
        "/secondary/doses/new", data=data, follow_redirects=False,
    )
    assert result.status_code == 303
    assert result.headers["location"] == "/secondary/doses"

    doses, vials, tokens = _state(root, 2)
    assert doses == [(1, 3.0, "mg", 3000.0, "dose", "Abdomen lower left")]
    assert vials == [("in_use",)]
    assert tokens == 1
    assert _state(root, 3)[0] == []
    assert not (root / "tracker.db").exists()

    after = client.get("/secondary/doses/new")
    assert "7000 mcg available" in after.text
    history = client.get("/secondary/doses")
    assert history.status_code == 200
    assert "PRIVATE-COMPOUND-2" in history.text
    assert "PRIVATE-DOSE-NOTES" not in history.text


def test_second_user_sees_only_own_vial_and_doses(browser):
    client, root = browser
    _login(client, 2)
    assert client.post(
        "/secondary/doses/new", data=_dose_form(client),
        follow_redirects=False,
    ).status_code == 303

    _login(client, 3)
    page = client.get("/secondary/doses/new")
    assert page.status_code == 200
    assert "PRIVATE-VIAL-3" in page.text
    assert "PRIVATE-VIAL-2" not in page.text
    assert "&lt;img" in page.text
    assert '<img src=x' not in page.text

    data = _dose_form(client)
    data["amount"] = "2"
    assert client.post(
        "/secondary/doses/new", data=data,
        follow_redirects=False,
    ).status_code == 303

    assert _state(root, 2)[0][0][1] == 3.0
    assert _state(root, 3)[0][0][1] == 2.0
    assert "PRIVATE-COMPOUND-2" not in client.get("/secondary/doses").text


def test_replay_and_different_payload_with_same_token_are_rejected(browser):
    client, root = browser
    _login(client, 2)
    data = _dose_form(client)
    assert client.post(
        "/secondary/doses/new", data=data,
        follow_redirects=False,
    ).status_code == 303

    assert client.post("/secondary/doses/new", data=data).status_code == 409
    assert client.post(
        "/secondary/doses/new", data={**data, "amount": "4"},
    ).status_code == 409
    assert len(_state(root, 2)[0]) == 1
    assert _state(root, 2)[2] == 1


def test_overdraw_incompatible_unit_and_invalid_vial_fail_without_mutating(browser):
    client, root = browser
    _login(client, 2)
    data = _dose_form(client)

    for changes in (
        {"amount": "11"},
        {"unit": "IU"},
        {"unit": "bad"},
        {"vial_id": "9999"},
        {"amount": "-1"},
        {"amount": "NaN"},
        {"taken_at": "invalid"},
        {"site": "Unknown"},
        {"amount": "0"},
    ):
        result = client.post(
            "/secondary/doses/new", data={**data, **changes},
        )
        assert result.status_code == 422, (changes, result.text[:120])
        assert _state(root, 2)[0] == []
        assert _state(root, 2)[2] == 0

    assert _state(root, 3)[0] == []


def test_remaining_stock_enforced_under_concurrent_requests(browser):
    _, root = browser
    payload = {
        "vial_id": 1,
        "taken_at": datetime.now().strftime("%Y-%m-%dT%H:%M"),
        "amount": 6.0, "unit": "mg",
        "site": "", "notes": "",
        "submission_token": str(uuid4()),
    }
    second = {**payload, "submission_token": str(uuid4())}

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [
            executor.submit(request_dose434, 2, "create_dose", item, root)
            for item in (payload, second)
        ]
        results = [future.result() for future in futures]

    assert sorted(x["status"] for x in results) == ["created", "rejected"]
    assert _state(root, 2)[0][0][3] == 6000.0
    assert len(_state(root, 2)[0]) == 1
    assert _state(root, 2)[2] == 1


def test_invalid_csrf_cross_site_and_forged_fields_do_not_write(browser):
    client, root = browser
    _login(client, 2)
    data = _dose_form(client)

    assert client.post(
        "/secondary/doses/new",
        data={**data, "csrf_token": "forged"},
    ).status_code == 403

    assert client.post(
        "/secondary/doses/new",
        headers={"Sec-Fetch-Site": "cross-site"},
        data=data,
    ).status_code == 403

    for injected in (
        {"user_id": "3"},
        {"database": "/opt/tracker/data/tracker.db"},
        {"sql": "DROP TABLE dose_logs"},
        {"kind": "waste"},
        {"supply_id_used": "1"},
    ):
        response = client.post(
            "/secondary/doses/new", data={**data, **injected},
        )
        assert response.status_code == 422

    assert client.post(
        "/secondary/doses/new?user_id=3", data=data,
    ).status_code == 400
    assert _state(root, 2)[0] == []


def test_disabled_and_unauthenticated_users_cannot_write(browser, monkeypatch):
    client, root = browser
    assert client.get(
        "/secondary/doses/new", follow_redirects=False,
    ).status_code == 303
    assert client.post("/secondary/doses/new", data={}).status_code == 401

    _login(client, 2)
    data = _dose_form(client)
    monkeypatch.delenv("TRACKER_SECONDARY_DOSE_WRITES434")

    assert client.get("/secondary/doses/new").status_code == 404
    assert client.post("/secondary/doses/new", data=data).status_code == 404
    assert client.get("/secondary/doses").status_code == 200
    assert _state(root, 2)[0] == []

    monkeypatch.setenv("TRACKER_SECONDARY_DOSE_WRITES434", "1")
    monkeypatch.setattr(config, "instance_label", lambda: "PROD")
    assert client.post("/secondary/doses/new", data=data).status_code == 404


def test_workspace_marker_tampering_rejects_write_before_child_launch(browser):
    client, root = browser
    _login(client, 2)
    data = _dose_form(client)

    with sqlite3.connect(root / "users" / "2" / "tracker.db") as conn:
        conn.execute("""
            UPDATE tracker_staged_workspace426 SET user_id=3
        """)
    assert client.post("/secondary/doses/new", data=data).status_code == 401
    assert _state(root, 2)[0] == []


@pytest.mark.parametrize("raw", (
    b"",
    b"[]",
    b'{"action":"options","user_id":3}',
    b'{"action":"create_dose","sql":"DELETE FROM doses","payload":{}}',
    b'{"action":"create_dose","payload":{"database":"/root"}}',
    b'{"action":"options","action":"options"}',
    b"x" * 4097,
))
def test_private_worker_request_is_exact_and_bounded(raw):
    with pytest.raises(ValueError):
        parse_request434(raw)


def test_parent_cannot_target_admin_database_or_arbitrary_operations(browser):
    _, root = browser
    with pytest.raises(PermissionError):
        request_dose434(1, "options", data_root=root)
    with pytest.raises(ValueError):
        request_dose434(2, "sql", data_root=root)


def test_private_vital_and_dose_permissions_are_independent(browser, monkeypatch):
    client, _ = browser
    _login(client, 2)

    # This release does not enable vital writes.
    monkeypatch.delenv("TRACKER_SECONDARY_VITAL_WRITES433")
    assert client.get("/secondary/vitals/new").status_code == 404
    assert client.get("/secondary/doses/new").status_code == 200


def test_middleware_exemption_matches_only_opted_in_dose_form():
    from pathlib import Path
    source = Path("app/main.py").read_text()
    assert 'secondary_preview430.dose_writes_enabled434()' in source
    assert 'request.url.path == "/secondary/doses/new"' in source
    assert 'and not secondary_form_post433' in source
