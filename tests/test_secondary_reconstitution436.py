"""Release 436: one-time private reconstitution and transaction safety."""

import re
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app import config, session_auth385 as auth
from app.secondary_preview430 import preview_app
from app.user_bootstrap426 import initialize_staged_workspace426
from app.user_accounts427 import stage_secondary_account427
from app.worker_reconstitution436 import (
    parse_request436, request_reconstitution436,
)
from app.worker_dose_write434 import request_dose434


@pytest.fixture
def browser(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(config, "instance_label", lambda: "DEV")
    monkeypatch.setenv("TRACKER_SECONDARY_PREVIEW430", "1")
    monkeypatch.setenv("TRACKER_SECONDARY_RECONSTITUTION_WRITES436", "1")
    monkeypatch.setenv("TRACKER_SECONDARY_DOSE_WRITES434", "1")
    auth.bootstrap("operator", "administrator-secure-password-436")
    (tmp_path / auth.FLAG).write_text("DEV enabled")

    for uid in (2, 3):
        initialize_staged_workspace426(uid, tmp_path)
        stage_secondary_account427(
            uid, f"member-{uid}", f"secondary-secure-password-{uid}-436",
        )
        with sqlite3.connect(tmp_path / "users" / str(uid) / "tracker.db") as conn:
            name = "PRIVATE-USER-TWO" if uid == 2 else '<img src=x onerror="x">'
            conn.execute("""
                INSERT INTO compounds(name,category,notes,primary_unit)
                VALUES (?, 'peptide', '', 'mg')
            """, (name,))
            conn.execute("""
                INSERT INTO vials
                    (compound_id,label,lot,cap_color,kit_ref,form,content_value,
                     content_unit,status,use_coa_content,unit_price_cents,notes,
                     storage_notes)
                VALUES (1, ?, '', '', '', 'lyophilized', 10, 'mg',
                        'sealed', 0, 0, '', '')
            """, (f"PRIVATE-VIAL-{uid}",))
            if uid == 2:
                conn.execute("""
                    INSERT INTO vials
                        (compound_id,label,lot,cap_color,kit_ref,form,
                         content_value,content_unit,volume_ml,status,
                         use_coa_content,unit_price_cents,notes,storage_notes)
                    VALUES (1, 'SOLUTION-VIAL', '', '', '', 'solution',
                            10, 'mg', 2.0, 'sealed', 0, 0, '', '')
                """)

    host = FastAPI()
    host.mount("/secondary", preview_app)
    with TestClient(host, base_url="https://tracker.test") as client:
        yield client, tmp_path


def _field(html, key):
    found = re.search(
        rf'name="{re.escape(key)}"\s+value="([^"]+)"', html,
    )
    assert found is not None, f"Missing {key}"
    return found.group(1)


def _login(client, uid):
    page = client.get("/secondary/login")
    assert page.status_code == 200
    result = client.post(
        "/secondary/login", data={
            "username": f"member-{uid}",
            "password": f"secondary-secure-password-{uid}-436",
            "csrf_token": _field(page.text, "csrf_token"),
        }, follow_redirects=False,
    )
    assert result.status_code == 303


def _form(client):
    response = client.get("/secondary/reconstitution")
    assert response.status_code == 200, response.text[:200]
    assert 'action="/secondary/reconstitution"' in response.text
    return {
        "csrf_token": _field(response.text, "csrf_token"),
        "submission_token": _field(response.text, "submission_token"),
        "vial_id": "1",
        "volume_ml": "2.0",
    }


def _state(root, uid):
    path = root / "users" / str(uid) / "tracker.db"
    with sqlite3.connect(path) as conn:
        vial = conn.execute("""
            SELECT id,volume_ml,reconstituted_on,status
            FROM vials WHERE id=1
        """).fetchone()
        events = conn.execute("""
            SELECT vial_id,kind,notes
            FROM preparation_events ORDER BY id
        """).fetchall()
        uses = conn.execute(
            "SELECT COUNT(*) FROM supply_usages"
        ).fetchone()[0]
        tokens = conn.execute("""
            SELECT COUNT(*) FROM inventory_submissions
            WHERE operation='secondary_reconstitute436'
        """).fetchone()[0]
        doses = conn.execute(
            "SELECT entered_value,entered_unit,amount_base FROM dose_logs"
        ).fetchall()
    return vial, events, uses, tokens, doses


def test_record_volume_event_and_then_dose_by_ml_without_other_user_change(browser):
    client, root = browser
    _login(client, 2)
    page = client.get("/secondary/reconstitution")
    assert "PRIVATE-VIAL-2" in page.text
    assert "SOLUTION-VIAL" not in page.text
    assert "PRIVATE-VIAL-3" not in page.text

    form = _form(client)
    response = client.post(
        "/secondary/reconstitution", data=form, follow_redirects=False,
    )
    assert response.status_code == 303
    assert response.headers["location"] == "/secondary/inventory"

    vial, events, uses, tokens, doses = _state(root, 2)
    assert vial[1] == 2.0
    assert vial[2] is not None
    assert vial[3] == "in_use"
    assert len(events) == 1
    assert events[0][0:2] == (1, "reconstitution")
    assert "no supplies deducted" in events[0][2]
    assert (uses, tokens, doses) == (0, 1, [])
    assert _state(root, 3)[0][1] is None
    assert not (root / "tracker.db").exists()

    from datetime import datetime
    report = request_dose434(2, "create_dose", {
        "vial_id": 1,
        "taken_at": datetime.now().strftime("%Y-%m-%dT%H:%M"),
        "amount": 0.5,
        "unit": "mL",
        "site": "",
        "notes": "",
        "submission_token": str(uuid4()),
    }, root)
    assert report["status"] == "created"
    assert _state(root, 2)[4] == [(0.5, "mL", 2500.0)]
    assert _state(root, 3)[4] == []


def test_other_user_can_only_reconstitute_their_own_vial(browser):
    client, root = browser
    _login(client, 2)
    assert client.post(
        "/secondary/reconstitution", data=_form(client),
        follow_redirects=False,
    ).status_code == 303
    _login(client, 3)
    page = client.get("/secondary/reconstitution")
    assert page.status_code == 200
    assert "PRIVATE-VIAL-3" in page.text
    assert "PRIVATE-VIAL-2" not in page.text
    assert "&lt;img" in page.text
    assert '<img src=x' not in page.text

    assert client.post(
        "/secondary/reconstitution", data=_form(client),
        follow_redirects=False,
    ).status_code == 303
    assert len(_state(root, 2)[1]) == 1
    assert len(_state(root, 3)[1]) == 1


def test_replay_conflict_and_new_token_cannot_reconstitute_twice(browser):
    client, root = browser
    _login(client, 2)
    form = _form(client)
    assert client.post(
        "/secondary/reconstitution", data=form,
        follow_redirects=False,
    ).status_code == 303
    assert client.post("/secondary/reconstitution", data=form).status_code == 409
    assert client.post(
        "/secondary/reconstitution", data={**form, "volume_ml": "3"},
    ).status_code == 409
    assert client.post(
        "/secondary/reconstitution",
        data={**form, "submission_token": str(uuid4())},
    ).status_code == 422
    assert len(_state(root, 2)[1]) == 1
    assert _state(root, 2)[3] == 1


def test_simultaneous_submissions_record_only_one_preparation(browser):
    _, root = browser
    first = {"vial_id": 1, "volume_ml": 2.0, "submission_token": str(uuid4())}
    second = {"vial_id": 1, "volume_ml": 3.0, "submission_token": str(uuid4())}
    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [
            executor.submit(
                request_reconstitution436, 2, "reconstitute", payload, root,
            )
            for payload in (first, second)
        ]
        statuses = sorted(f.result()["status"] for f in futures)
    assert statuses == ["created", "rejected"]
    vial, events, uses, tokens, _ = _state(root, 2)
    assert vial[1] in (2.0, 3.0)
    assert len(events) == 1
    assert (uses, tokens) == (0, 1)


def test_invalid_values_injected_fields_and_csrf_never_change_volume(browser):
    client, root = browser
    _login(client, 2)
    data = _form(client)

    for change in (
        {"volume_ml": "0"},
        {"volume_ml": "-1"},
        {"volume_ml": "NaN"},
        {"volume_ml": "1001"},
        {"volume_ml": ""},
        {"volume_ml": "inf"},
        {"vial_id": "999"},
        {"vial_id": "2"},
        {"vial_id": "xyz"},
        {"user_id": "3"},
        {"database": "/opt/tracker/data/tracker.db"},
        {"sql": "DELETE FROM vials"},
        {"supply_id": "1"},
    ):
        result = client.post(
            "/secondary/reconstitution", data={**data, **change},
        )
        assert result.status_code == 422, (change, result.status_code)
    assert client.post(
        "/secondary/reconstitution",
        data={**data, "csrf_token": "bad"},
    ).status_code == 403
    assert client.post(
        "/secondary/reconstitution", data=data,
        headers={"Sec-Fetch-Site": "cross-site"},
    ).status_code == 403
    assert client.post(
        "/secondary/reconstitution?user_id=3", data=data,
    ).status_code == 400
    assert _state(root, 2)[0][1] is None
    assert _state(root, 2)[1] == []
    assert _state(root, 3)[1] == []


def test_disabled_in_prod_and_when_flag_absent(browser, monkeypatch):
    client, root = browser
    assert client.get(
        "/secondary/reconstitution", follow_redirects=False,
    ).status_code == 303
    assert client.post("/secondary/reconstitution", data={}).status_code == 401
    _login(client, 2)
    data = _form(client)
    monkeypatch.delenv("TRACKER_SECONDARY_RECONSTITUTION_WRITES436", raising=False)
    assert client.get("/secondary/reconstitution").status_code == 404
    assert client.post(
        "/secondary/reconstitution", data=data,
    ).status_code == 404
    assert 'href="/secondary/reconstitution"' not in client.get(
        "/secondary/inventory"
    ).text
    assert _state(root, 2)[1] == []

    monkeypatch.setenv("TRACKER_SECONDARY_RECONSTITUTION_WRITES436", "1")
    monkeypatch.setattr(config, "instance_label", lambda: "PROD")
    assert client.get("/secondary/reconstitution").status_code == 200
    assert client.post(
        "/secondary/reconstitution", data=data,
    ).status_code == 403


def test_tampered_workspace_marker_blocks_reconstitution(browser):
    client, root = browser
    _login(client, 2)
    data = _form(client)
    with sqlite3.connect(root / "users" / "2" / "tracker.db") as conn:
        conn.execute("UPDATE tracker_staged_workspace426 SET user_id=3")
    assert client.post(
        "/secondary/reconstitution", data=data,
    ).status_code == 401
    assert _state(root, 2)[1] == []


@pytest.mark.parametrize("raw", (
    b"",
    b"[]",
    b'{"action":"options","user_id":3}',
    b'{"action":"reconstitute","database":"/tmp/a","payload":{}}',
    b'{"action":"reconstitute","payload":{"sql":"DROP TABLE vials"}}',
    b'{"action":"options","action":"options"}',
    b"x" * 1025,
))
def test_worker_accepts_no_sql_or_caller_identity(raw):
    with pytest.raises(ValueError):
        parse_request436(raw)


def test_admin_identity_and_unknown_operation_denied(browser):
    _, root = browser
    with pytest.raises(PermissionError):
        request_reconstitution436(1, "options", data_root=root)
    with pytest.raises(ValueError):
        request_reconstitution436(2, "sql", data_root=root)


def test_existing_dose_history_cannot_be_reconstituted(browser):
    client, root = browser
    _login(client, 2)
    from datetime import datetime
    dose = request_dose434(2, "create_dose", {
        "vial_id": 1, "taken_at": datetime.now().strftime("%Y-%m-%dT%H:%M"),
        "amount": 1.0, "unit": "mg", "site": "", "notes": "",
        "submission_token": str(uuid4()),
    }, root)
    assert dose["status"] == "created"
    form = _form(client)
    assert client.post(
        "/secondary/reconstitution", data=form,
    ).status_code == 422
    assert _state(root, 2)[0][1] is None
    assert _state(root, 2)[1] == []


def test_parent_app_middleware_has_only_exact_gated_form_exemption():
    from pathlib import Path
    source = Path("app/main.py").read_text()
    assert 'secondary_preview430.reconstitution_enabled436()' in source
    assert 'request.url.path == "/secondary/reconstitution"' in source
    assert "and not secondary_form_post433" in source
