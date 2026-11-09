"""Release 437: private stock reconciliation and auditable vial corrections."""

import json
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
from app.worker_reconciliation437 import (
    parse_request437,
    request_reconciliation437,
)


@pytest.fixture
def browser(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(config, "instance_label", lambda: "DEV")
    monkeypatch.setenv("TRACKER_SECONDARY_PREVIEW430", "1")
    monkeypatch.setenv("TRACKER_SECONDARY_VIAL_CORRECTIONS437", "1")

    auth.bootstrap("operator", "administrator-secure-password-437")
    (tmp_path / auth.FLAG).write_text("DEV enabled")

    for uid in (2, 3):
        initialize_staged_workspace426(uid, tmp_path)
        stage_secondary_account427(
            uid, f"member-{uid}", f"secondary-secure-password-{uid}-437",
        )
        with sqlite3.connect(tmp_path / "users" / str(uid) / "tracker.db") as db:
            compound = (
                "PRIVATE-ALPHA-437"
                if uid == 2 else '<img src=x onerror="bad">'
            )
            db.execute("""
                INSERT INTO compounds(name,category,notes,primary_unit)
                VALUES (?, 'peptide', '', 'mg')
            """, (compound,))
            db.execute("""
                INSERT INTO vials
                    (compound_id,label,lot,cap_color,kit_ref,form,
                     content_value,content_unit,status,use_coa_content,
                     unit_price_cents,notes,storage_notes)
                VALUES (1, ?, '', '', '', 'lyophilized',
                        10, 'mg', 'in_use', 0, 0, '', '')
            """, (f"IN-USE-{uid}",))
            db.execute("""
                INSERT INTO vials
                    (compound_id,label,lot,cap_color,kit_ref,form,
                     content_value,content_unit,status,use_coa_content,
                     unit_price_cents,notes,storage_notes)
                VALUES (1, ?, '', '', '', 'lyophilized',
                        5, 'mg', 'sealed', 0, 0, '', '')
            """, (f"SEALED-{uid}",))
            if uid == 2:
                db.execute("""
                    INSERT INTO dose_logs
                        (vial_id,taken_at,entered_value,entered_unit,
                         amount_base,kind,site,notes)
                    VALUES (1, ?, 3, 'mg', 3000, 'dose', '', '')
                """, (datetime.now().strftime("%Y-%m-%d %H:%M:%S"),))

    host = FastAPI()
    host.mount("/secondary", preview_app)
    with TestClient(host, base_url="https://tracker.test") as client:
        yield client, tmp_path


def _hidden(html, name):
    found = re.search(
        rf'name="{re.escape(name)}"\s+value="([^"]+)"',
        html,
    )
    assert found is not None, f"Missing form field: {name}"
    return found.group(1)


def _login(client, uid):
    page = client.get("/secondary/login")
    assert page.status_code == 200
    result = client.post(
        "/secondary/login",
        data={
            "username": f"member-{uid}",
            "password": f"secondary-secure-password-{uid}-437",
            "csrf_token": _hidden(page.text, "csrf_token"),
        },
        follow_redirects=False,
    )
    assert result.status_code == 303


def _form(client, vial_id=2):
    result = client.get(f"/secondary/reconcile/vials/{vial_id}")
    assert result.status_code == 200, result.text[:200]
    assert 'action="/secondary/reconcile/correct"' in result.text
    return {
        "csrf_token": _hidden(result.text, "csrf_token"),
        "submission_token": _hidden(result.text, "submission_token"),
        "vial_id": str(vial_id),
        "snapshot": _hidden(result.text, "snapshot"),
        "label": f"SEALED-2" if vial_id == 2 else "IN-USE-2",
        "lot": "",
        "cap_color": "",
        "status": "sealed" if vial_id == 2 else "in_use",
        "reason": "Correct physical-vial identification",
    }


def _db(root, uid):
    return sqlite3.connect(root / "users" / str(uid) / "tracker.db")


def _state(root, uid, vid=2):
    with _db(root, uid) as conn:
        vial = conn.execute("""
            SELECT label,lot,cap_color,status,content_value,content_unit,
                   volume_ml FROM vials WHERE id=?
        """, (vid,)).fetchone()
        audit = conn.execute("""
            SELECT action,before_json,after_json
            FROM change_audit
            WHERE entity_type='vial' AND entity_id=?
            ORDER BY id
        """, (vid,)).fetchall()
        tokens = conn.execute("""
            SELECT COUNT(*) FROM inventory_submissions
            WHERE operation='secondary_vial_correction437'
        """).fetchone()[0]
        doses = conn.execute("SELECT COUNT(*) FROM dose_logs").fetchone()[0]
    return vial, audit, tokens, doses


def test_reconciliation_report_is_read_only_private_and_shows_stock(browser):
    client, root = browser
    _login(client, 2)
    page = client.get("/secondary/reconcile")
    assert page.status_code == 200
    assert "PRIVATE-ALPHA-437" in page.text
    assert "IN-USE-2" in page.text
    assert "SEALED-2" in page.text
    assert "IN-USE-3" not in page.text
    assert "7 mg" in page.text
    assert "3 mg" in page.text
    assert page.headers["cache-control"] == "no-store"

    data = request_reconciliation437(2, "report", data_root=root)
    assert len(data["items"]) == 2
    use = next(item for item in data["items"] if item["id"] == 1)
    assert (use["total"], use["used"], use["remaining"]) == (10.0, 3.0, 7.0)
    assert not use["warnings"]
    assert _state(root, 2)[1:] == ([], 0, 1)
    assert not (root / "tracker.db").exists()


def test_audited_metadata_and_one_way_discard_are_atomic(browser):
    client, root = browser
    _login(client, 2)
    form = _form(client)
    form.update({
        "label": "CORRECTED-VIAL-437",
        "lot": "LOT-437",
        "cap_color": "purple",
        "status": "discarded",
        "reason": "Physically discarded after inspection",
    })
    reply = client.post(
        "/secondary/reconcile/correct",
        data=form, follow_redirects=False,
    )
    assert reply.status_code == 303, reply.text[:300]
    assert reply.headers["location"] == "/secondary/reconcile/vials/2"

    vial, events, tokens, doses = _state(root, 2)
    assert vial == (
        "CORRECTED-VIAL-437", "LOT-437", "purple",
        "discarded", 5.0, "mg", None,
    )
    assert (tokens, doses) == (1, 1)
    assert len(events) == 1
    action, before, after = events[0]
    assert action == "secondary_correction437"
    before, after = json.loads(before), json.loads(after)
    assert before["label"] == "SEALED-2"
    assert after["label"] == "CORRECTED-VIAL-437"
    assert before["status"] == "sealed"
    assert after["status"] == "discarded"
    assert after["_reason"] == "Physically discarded after inspection"
    assert _state(root, 3)[1] == []

    summary = client.get("/secondary/reconcile").text
    assert "Closed vial has unused recorded stock" in summary
    detail = client.get("/secondary/reconcile/vials/2").text
    assert "Recent Audit History" in detail
    assert "Physically discarded after inspection" in detail


def test_lifecycle_transition_guards_and_no_change_are_rejected(browser):
    client, root = browser
    _login(client, 2)

    sealed = _form(client)
    sealed.update({"status": "finished", "reason": "Lifecycle transition test"})
    assert client.post("/secondary/reconcile/correct", data=sealed).status_code == 422

    in_use = _form(client, vial_id=1)
    in_use.update({"status": "sealed", "reason": "Attempt reversal of vial state"})
    assert client.post("/secondary/reconcile/correct", data=in_use).status_code == 422

    unchanged = _form(client)
    assert client.post("/secondary/reconcile/correct", data=unchanged).status_code == 422
    assert _state(root, 2)[1:3] == ([], 0)
    assert _state(root, 2, 1)[1:3] == ([], 0)


def test_duplicate_token_payload_conflict_and_stale_form(browser):
    client, root = browser
    _login(client, 2)
    data = _form(client)
    data["label"] = "FIRST-CORRECTION-437"

    assert client.post(
        "/secondary/reconcile/correct", data=data,
        follow_redirects=False,
    ).status_code == 303
    assert client.post(
        "/secondary/reconcile/correct", data=data,
    ).status_code == 409
    assert client.post(
        "/secondary/reconcile/correct",
        data={**data, "label": "DIFFERENT-SAME-TOKEN"},
    ).status_code == 409
    assert client.post(
        "/secondary/reconcile/correct",
        data={**data, "submission_token": str(uuid4())},
    ).status_code == 409
    assert len(_state(root, 2)[1]) == 1
    assert _state(root, 2)[2] == 1


def test_stale_form_rejected_if_dose_inventory_changes(browser):
    client, root = browser
    _login(client, 2)
    data = _form(client, vial_id=1)
    data["label"] = "SHOULD-NOT-APPEAR"

    with _db(root, 2) as db:
        db.execute("""
            INSERT INTO dose_logs
                (vial_id,taken_at,entered_value,entered_unit,
                 amount_base,kind,site,notes)
            VALUES (1, ?, 1, 'mg', 1000, 'dose', '', '')
        """, (datetime.now().strftime("%Y-%m-%d %H:%M:%S"),))

    assert client.post(
        "/secondary/reconcile/correct", data=data,
    ).status_code == 409
    assert _state(root, 2, 1)[0][0] == "IN-USE-2"
    assert _state(root, 2, 1)[1] == []


def test_concurrent_corrections_reject_stale_snapshot(browser):
    client, root = browser
    _login(client, 2)
    data = _form(client)
    snapshot = data["snapshot"]
    jobs = [
        {
            "vial_id": 2, "snapshot": snapshot,
            "label": f"CONCURRENT-{i}", "lot": "",
            "cap_color": "", "status": "sealed",
            "reason": "Concurrent correction must serialize",
            "submission_token": str(uuid4()),
        }
        for i in (1, 2)
    ]
    with ThreadPoolExecutor(max_workers=2) as pool:
        tasks = [
            pool.submit(
                request_reconciliation437, 2, "correct",
                payload=payload, data_root=root,
            )
            for payload in jobs
        ]
        results = [task.result()["status"] for task in tasks]
    assert sorted(results) == ["created", "stale"]
    assert len(_state(root, 2)[1]) == 1
    assert _state(root, 2)[2] == 1
    assert _state(root, 3)[1] == []


def test_account_switch_and_html_escaping_protect_private_audit(browser):
    client, root = browser
    _login(client, 2)
    data = _form(client)
    data["label"] = '<img src=x onerror="bad">'
    data["reason"] = '<script>alert("bad")</script> corrected vial tag'
    assert client.post(
        "/secondary/reconcile/correct", data=data,
        follow_redirects=False,
    ).status_code == 303

    detail2 = client.get("/secondary/reconcile/vials/2")
    assert detail2.status_code == 200
    assert '&lt;img' in detail2.text
    assert "<img src=x" not in detail2.text
    assert "&lt;script&gt;" in detail2.text
    assert '<script>' not in detail2.text

    _login(client, 3)
    detail3 = client.get("/secondary/reconcile/vials/2")
    assert detail3.status_code == 200
    assert "SEALED-3" in detail3.text
    assert "PRIVATE-ALPHA-437" not in detail3.text
    assert "CONCURRENT" not in detail3.text
    assert 'onerror="bad"' not in detail3.text
    assert "&lt;img" in detail3.text
    assert _state(root, 3)[1] == []


def test_forged_fields_invalid_values_and_csrf_are_rejected(browser):
    client, root = browser
    _login(client, 2)
    data = _form(client)
    data["label"] = "CORRECTION"

    for invalid in (
        {"user_id": "3"},
        {"database": "/opt/tracker/data/tracker.db"},
        {"sql": "DROP TABLE dose_logs"},
        {"content_value": "900"},
        {"volume_ml": "4"},
        {"status": "in_use"},
        {"reason": "short"},
        {"snapshot": "fake"},
        {"vial_id": "999"},
        {"vial_id": "invalid"},
    ):
        response = client.post(
            "/secondary/reconcile/correct", data={**data, **invalid},
        )
        assert response.status_code in (409, 422), (invalid, response.status_code)

    assert client.post(
        "/secondary/reconcile/correct", data={**data, "csrf_token": "bad"},
    ).status_code == 403
    assert client.post(
        "/secondary/reconcile/correct", data=data,
        headers={"Sec-Fetch-Site": "cross-site"},
    ).status_code == 403
    assert client.post(
        "/secondary/reconcile/correct?user_id=3", data=data,
    ).status_code == 400
    assert client.get(
        "/secondary/reconcile?user_id=3",
    ).status_code == 400
    assert _state(root, 2)[1] == []
    assert _state(root, 3)[1] == []


def test_disabled_flag_keeps_reconciliation_read_only_and_prod_denied(browser, monkeypatch):
    client, root = browser
    _login(client, 2)
    data = _form(client)
    data["label"] = "CORRECTION"
    monkeypatch.delenv("TRACKER_SECONDARY_VIAL_CORRECTIONS437", raising=False)

    report = client.get("/secondary/reconcile")
    assert report.status_code == 200
    detail = client.get("/secondary/reconcile/vials/2")
    assert detail.status_code == 200
    assert 'action="/secondary/reconcile/correct"' not in detail.text
    assert client.post(
        "/secondary/reconcile/correct", data=data,
    ).status_code == 404
    assert _state(root, 2)[1] == []

    monkeypatch.setenv("TRACKER_SECONDARY_VIAL_CORRECTIONS437", "1")
    monkeypatch.setattr(config, "instance_label", lambda: "PROD")
    assert client.get("/secondary/reconcile").status_code == 200
    assert client.post(
        "/secondary/reconcile/correct", data=data,
    ).status_code == 200


def test_unauthenticated_and_admin_worker_identity_are_denied(browser):
    client, root = browser
    assert client.get(
        "/secondary/reconcile", follow_redirects=False,
    ).status_code == 303
    assert client.post(
        "/secondary/reconcile/correct", data={},
    ).status_code == 401
    with pytest.raises(PermissionError):
        request_reconciliation437(1, "report", data_root=root)
    with pytest.raises(ValueError):
        request_reconciliation437(2, "query", data_root=root)


@pytest.mark.parametrize("raw", (
    b"",
    b"[]",
    b'{"action":"report","user_id":3}',
    b'{"action":"detail","database":"/tmp/admin"}',
    b'{"action":"correct","payload":{"sql":"DELETE FROM vials"}}',
    b'{"action":"report","action":"report"}',
    b"x" * 4097,
))
def test_private_worker_rejects_forged_operations(raw):
    with pytest.raises(ValueError):
        parse_request437(raw)


def test_middleware_exempts_only_the_gated_correction_form():
    from pathlib import Path
    source = Path("app/main.py").read_text()
    assert "secondary_preview430.corrections_enabled437()" in source
    assert 'request.url.path == "/secondary/reconcile/correct"' in source
    assert "and not secondary_form_post433" in source
