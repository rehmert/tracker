"""Release 439 isolated pytest fixtures and exact original helper functions.

All test cases retain independent tmp_path workspaces and authentic
secondary account staging, session login and private worker launches.
"""

import json
import re
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, date
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app import config, session_auth385 as auth
from app.secondary_preview430 import preview_app
from app.user_accounts427 import stage_secondary_account427
from app.user_bootstrap426 import initialize_staged_workspace426
from app.worker_supply_use439 import (
    parse_request439, request_use439, validate_use439,
)


@pytest.fixture
def browser(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(config, "instance_label", lambda: "DEV")
    monkeypatch.setenv("TRACKER_SECONDARY_PREVIEW430", "1")
    monkeypatch.setenv("TRACKER_SECONDARY_SUPPLY_USE439", "1")
    auth.bootstrap("operator", "administrator-secure-password-439")
    (tmp_path / auth.FLAG).write_text("DEV enabled")

    for uid in (2, 3):
        initialize_staged_workspace426(uid, tmp_path)
        stage_secondary_account427(
            uid, f"member-{uid}", f"secondary-secure-password-{uid}-439",
        )
        dbpath = tmp_path / "users" / str(uid) / "tracker.db"
        with sqlite3.connect(dbpath) as db:
            db.execute("PRAGMA foreign_keys=ON")
            name = (
                "PRIVATE-COMPOUND-TWO" if uid == 2
                else '<img src=x onerror="bad">'
            )
            db.execute("""
                INSERT INTO compounds(name,category,notes,primary_unit)
                VALUES (?, 'peptide', '', 'mg')
            """, (name,))
            db.execute("""
                INSERT INTO vials
                    (compound_id,label,lot,cap_color,kit_ref,form,
                     content_value,content_unit,volume_ml,status,
                     use_coa_content,unit_price_cents,notes,storage_notes)
                VALUES (1, ?, '', '', '', 'lyophilized',
                        10, 'mg', 3, 'in_use', 0, 0, '', '')
            """, (f"PRIVATE-VIAL-{uid}",))
            for dose in (1, 2):
                db.execute("""
                    INSERT INTO dose_logs
                        (vial_id,taken_at,entered_value,entered_unit,
                         amount_base,kind,site,notes)
                    VALUES (1, ?, 1, 'mg', 1000, 'dose', '', '')
                """, (datetime.now().strftime("%Y-%m-%d %H:%M:%S"),))
            db.execute("""
                INSERT INTO preparation_events (vial_id,kind,notes)
                VALUES (1,'reconstitution','Added 3 mL')
            """)
            db.execute("""
                INSERT INTO purchases
                    (vendor,purchased_on,order_ref,shipping_cents,
                     tax_cents,discount_cents,notes)
                VALUES ('Private Intake',?,'test439',0,0,0,'')
            """, (date.today().isoformat(),))
            for kind, value, label in (
                ("bac_water", 10.0, f"PRIVATE-BAC-{uid}"),
                ("needle", 5.0, f"PRIVATE-NEEDLE-{uid}"),
                ("swab", 4.0, f"PRIVATE-SWAB-{uid}"),
                ("bac_water", 4.0, f"PRIVATE-BAC-SECOND-{uid}"),
            ):
                db.execute("""
                    INSERT INTO supplies
                        (purchase_id,name,kind,purchased_qty,remaining_qty,
                         unit_price_cents,notes)
                    VALUES (1,?,?,?,?,0,'')
                """, (label, kind, value, value))

    host = FastAPI()
    host.mount("/secondary", preview_app)
    with TestClient(host, base_url="https://tracker.test") as client:
        yield client, tmp_path


def _hidden(html, key):
    match = re.search(
        rf'name="{re.escape(key)}"\s+value="([^"]+)"', html,
    )
    assert match is not None, f"Missing hidden field {key}"
    return match.group(1)


def _login(client, uid):
    page = client.get("/secondary/login")
    assert page.status_code == 200
    response = client.post(
        "/secondary/login",
        data={
            "username": f"member-{uid}",
            "password": f"secondary-secure-password-{uid}-439",
            "csrf_token": _hidden(page.text, "csrf_token"),
        },
        follow_redirects=False,
    )
    assert response.status_code == 303


def _form(client, supply_id=2, reference="dose:1", amount="1"):
    page = client.get("/secondary/supplies/use")
    assert page.status_code == 200, page.text[:250]
    assert 'action="/secondary/supplies/use"' in page.text
    return {
        "csrf_token": _hidden(page.text, "csrf_token"),
        "submission_token": _hidden(page.text, "submission_token"),
        "supply_id": str(supply_id),
        "reference": reference,
        "amount": amount,
        "notes": "Actual supply use",
    }


def _db(root, uid):
    return sqlite3.connect(root / "users" / str(uid) / "tracker.db")


def _state(root, uid):
    with _db(root, uid) as db:
        stock = db.execute("""
            SELECT id,remaining_qty FROM supplies ORDER BY id
        """).fetchall()
        usages = db.execute("""
            SELECT id,supply_id,dose_id,vial_id,amount
            FROM supply_usages ORDER BY id
        """).fetchall()
        preparation_links = db.execute("""
            SELECT event_id,usage_id FROM preparation_supplies ORDER BY id
        """).fetchall()
        audit = db.execute("""
            SELECT action,before_json,after_json
            FROM change_audit WHERE entity_type='supply' ORDER BY id
        """).fetchall()
        tokens = db.execute("""
            SELECT COUNT(*) FROM inventory_submissions
            WHERE operation='secondary_supply_use439'
        """).fetchone()[0]
        doses = db.execute(
            "SELECT COUNT(*) FROM dose_logs"
        ).fetchone()[0]
    return stock, usages, preparation_links, audit, tokens, doses
