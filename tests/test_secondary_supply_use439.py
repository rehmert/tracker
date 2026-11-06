"""Release 439: linked private supply use and inventory-safe accounting."""

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


def test_needle_use_links_exact_dose_updates_stock_and_audit(browser):
    client, root = browser
    _login(client, 2)
    data = _form(client)
    result = client.post(
        "/secondary/supplies/use", data=data, follow_redirects=False,
    )
    assert result.status_code == 303, result.text[:250]
    assert result.headers["location"] == "/secondary/supplies/use"
    stock, usages, links, audit, tokens, doses = _state(root, 2)
    assert stock[1] == (2, 4.0)
    assert usages == [(1, 2, 1, 1, 1.0)]
    assert links == []
    assert tokens == 1 and doses == 2
    assert len(audit) == 1
    assert audit[0][0] == "secondary_supply_use439"
    after = json.loads(audit[0][2])
    assert after["deducted"] == 1.0
    assert after["reference_type"] == "dose"
    assert after["reference_id"] == 1
    assert after["remaining"] == 4.0
    assert _state(root, 3)[1] == []
    assert not (root / "tracker.db").exists()
    history = client.get("/secondary/supplies/use")
    assert "Recent Supply Use" in history.text
    assert "Dose #1" in history.text
    assert "PRIVATE-NEEDLE-2" in history.text


def test_bac_water_linked_to_preparation_and_volume_cap(browser):
    client, root = browser
    _login(client, 2)
    first = _form(
        client, supply_id=1, reference="reconstitution:1", amount="2.5",
    )
    assert client.post(
        "/secondary/supplies/use", data=first, follow_redirects=False,
    ).status_code == 303
    stock, uses, links, audit, tokens, doses = _state(root, 2)
    assert stock[0] == (1, 7.5)
    assert uses[0] == (1, 1, None, 1, 2.5)
    assert links == [(1, 1)]
    assert tokens == 1 and doses == 2
    assert len(audit) == 1

    excess = _form(
        client, supply_id=4, reference="reconstitution:1", amount="1",
    )
    assert client.post("/secondary/supplies/use", data=excess).status_code == 422
    assert _state(root, 2)[1] == uses

    exact = _form(
        client, supply_id=4, reference="reconstitution:1", amount="0.5",
    )
    assert client.post(
        "/secondary/supplies/use", data=exact, follow_redirects=False,
    ).status_code == 303
    result = _state(root, 2)
    assert result[0][3] == (4, 3.5)
    assert len(result[1]) == 2 and len(result[2]) == 2
    assert result[4] == 2
    assert _state(root, 3)[2] == []


def test_invalid_links_and_overdraw_cannot_mutate_stock(browser):
    client, root = browser
    _login(client, 2)
    data = _form(client)

    for invalid in (
        {"supply_id": "999"},
        {"supply_id": "not-an-id"},
        {"reference": "dose:999"},
        {"reference": "reconstitution:999"},
        {"reference": "admin:1"},
        {"reference": "dose:-1"},
        {"supply_id": "1", "reference": "dose:1"},
        {"amount": "0"},
        {"amount": "-1"},
        {"amount": "NaN"},
        {"amount": "6"},
        {"amount": "1.5"},
        {"supply_id": "1", "reference": "reconstitution:1", "amount": "4"},
        {"user_id": "3"},
        {"sql": "SELECT * FROM supplies"},
        {"database": "/opt/tracker/data/tracker.db"},
    ):
        reply = client.post("/secondary/supplies/use", data={**data, **invalid})
        assert reply.status_code == 422, (invalid, reply.status_code, reply.text[:100])
    assert _state(root, 2)[1] == []
    assert _state(root, 3)[1] == []


def test_replay_and_same_supply_reference_link_are_rejected(browser):
    client, root = browser
    _login(client, 2)
    data = _form(client)
    assert client.post(
        "/secondary/supplies/use", data=data, follow_redirects=False,
    ).status_code == 303
    assert client.post("/secondary/supplies/use", data=data).status_code == 409
    assert client.post(
        "/secondary/supplies/use", data={**data, "amount": "2"},
    ).status_code == 409
    assert client.post(
        "/secondary/supplies/use",
        data={**data, "submission_token": str(uuid4())},
    ).status_code == 422
    assert len(_state(root, 2)[1]) == 1
    assert _state(root, 2)[4] == 1


def test_concurrent_supply_requests_cannot_overdraw(browser):
    _, root = browser
    payloads = [
        {
            "supply_id": 2,
            "reference_type": "dose",
            "reference_id": dose,
            "amount": 4.0,
            "notes": "",
            "submission_token": str(uuid4()),
        }
        for dose in (1, 2)
    ]
    with ThreadPoolExecutor(max_workers=2) as pool:
        jobs = [
            pool.submit(request_use439, 2, "use", item, root)
            for item in payloads
        ]
        statuses = sorted(job.result()["status"] for job in jobs)

    assert statuses == ["created", "rejected"]
    stock, uses, _, audit, tokens, _ = _state(root, 2)
    assert stock[1] == (2, 1.0)
    assert len(uses) == len(audit) == tokens == 1
    assert _state(root, 3)[1] == []


def test_accounts_have_independent_stock_and_escaped_labels(browser):
    client, root = browser
    _login(client, 2)
    assert client.post(
        "/secondary/supplies/use", data=_form(client),
        follow_redirects=False,
    ).status_code == 303

    _login(client, 3)
    page = client.get("/secondary/supplies/use")
    assert page.status_code == 200
    assert "PRIVATE-NEEDLE-3" in page.text
    assert "PRIVATE-NEEDLE-2" not in page.text
    assert "&lt;img" in page.text
    assert "<img src=x" not in page.text
    assert "Recent Supply Use" in page.text
    assert "No supply consumption recorded yet" in page.text

    own = _form(client, supply_id=2, reference="dose:1")
    assert client.post(
        "/secondary/supplies/use", data=own, follow_redirects=False,
    ).status_code == 303
    assert _state(root, 2)[0][1] == (2, 4.0)
    assert _state(root, 3)[0][1] == (2, 4.0)
    assert len(_state(root, 2)[1]) == len(_state(root, 3)[1]) == 1


def test_csrf_fetch_site_unauthenticated_and_flags(browser, monkeypatch):
    client, root = browser
    assert client.get(
        "/secondary/supplies/use", follow_redirects=False,
    ).status_code == 303
    assert client.post("/secondary/supplies/use", data={}).status_code == 401
    _login(client, 2)
    form = _form(client)
    assert client.post(
        "/secondary/supplies/use",
        data={**form, "csrf_token": "forged"},
    ).status_code == 403
    assert client.post(
        "/secondary/supplies/use",
        data=form, headers={"Sec-Fetch-Site": "cross-site"},
    ).status_code == 403
    assert client.post(
        "/secondary/supplies/use?user_id=3", data=form,
    ).status_code == 400

    monkeypatch.delenv("TRACKER_SECONDARY_SUPPLY_USE439", raising=False)
    assert client.get("/secondary/supplies/use").status_code == 404
    assert client.post("/secondary/supplies/use", data=form).status_code == 404
    assert client.get("/secondary/supplies").status_code == 200
    assert 'href="/secondary/supplies/use"' not in (
        client.get("/secondary/supplies").text
    )
    assert _state(root, 2)[1] == []
    monkeypatch.setenv("TRACKER_SECONDARY_SUPPLY_USE439", "1")
    monkeypatch.setattr(config, "instance_label", lambda: "PROD")
    assert client.get("/secondary/supplies/use").status_code == 404
    assert client.post("/secondary/supplies/use", data=form).status_code == 404


@pytest.mark.parametrize("raw", (
    b"",
    b"[]",
    b'{"action":"options","user_id":3}',
    b'{"action":"use","database":"/tmp/admin","payload":{}}',
    b'{"action":"use","payload":{"sql":"SELECT * FROM users"}}',
    b'{"action":"options","action":"options"}',
    b"x" * 4097,
))
def test_worker_rejects_unknown_actions_and_paths(raw):
    with pytest.raises(ValueError):
        parse_request439(raw)


def test_parent_rejects_administrator_and_generic_operations(browser):
    _, root = browser
    with pytest.raises(PermissionError):
        request_use439(1, "options", data_root=root)
    with pytest.raises(ValueError):
        request_use439(2, "sql", data_root=root)


def test_source_middleware_is_narrow_and_gated():
    from pathlib import Path
    source = Path("app/main.py").read_text()
    assert 'secondary_preview430.supply_use_enabled439()' in source
    assert 'request.url.path == "/secondary/supplies/use"' in source
    assert "and not secondary_form_post433" in source
