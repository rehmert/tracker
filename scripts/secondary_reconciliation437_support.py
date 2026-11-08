"""Release 437 isolated pytest fixtures and exact original helper functions.

All test cases retain independent tmp_path workspaces and authentic
secondary account staging, session login and private worker launches.
"""

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
