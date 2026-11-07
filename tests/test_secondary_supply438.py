"""Release 438: private supply intake, read-only inventory and isolation."""

import re
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app import config, session_auth385 as auth
from app.secondary_preview430 import preview_app
from app.user_accounts427 import stage_secondary_account427
from app.user_bootstrap426 import initialize_staged_workspace426
from app.worker_supply438 import (
    parse_request438, request_supply438, validate_create438,
)


@pytest.fixture
def browser(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(config, "instance_label", lambda: "DEV")
    monkeypatch.setenv("TRACKER_SECONDARY_PREVIEW430", "1")
    monkeypatch.setenv("TRACKER_SECONDARY_SUPPLY_WRITES438", "1")
    auth.bootstrap("operator", "administrator-secure-password-438")
    (tmp_path / auth.FLAG).write_text("DEV enabled")
    for uid in (2, 3):
        initialize_staged_workspace426(uid, tmp_path)
        stage_secondary_account427(
            uid, f"member-{uid}", f"secondary-secure-password-{uid}-438",
        )
    host = FastAPI()
    host.mount("/secondary", preview_app)
    with TestClient(host, base_url="https://tracker.test") as client:
        yield client, tmp_path


def _hidden(html, key):
    match = re.search(rf'name="{re.escape(key)}"\s+value="([^"]+)"', html)
    assert match is not None, f"Missing hidden form field {key}"
    return match.group(1)


def _login(client, uid):
    page = client.get("/secondary/login")
    assert page.status_code == 200
    reply = client.post(
        "/secondary/login",
        data={
            "username": f"member-{uid}",
            "password": f"secondary-secure-password-{uid}-438",
            "csrf_token": _hidden(page.text, "csrf_token"),
        }, follow_redirects=False,
    )
    assert reply.status_code == 303


def _form(client, kind="bac_water", quantity="25"):
    page = client.get("/secondary/supplies")
    assert page.status_code == 200
    assert 'action="/secondary/supplies"' in page.text
    return {
        "csrf_token": _hidden(page.text, "csrf_token"),
        "submission_token": _hidden(page.text, "submission_token"),
        "name": "PRIVATE-SUPPLY-438",
        "kind": kind, "quantity": quantity, "notes": "Private inventory intake",
    }


def _db(root, uid):
    return sqlite3.connect(root / "users" / str(uid) / "tracker.db")


def _state(root, uid):
    with _db(root, uid) as connection:
        purchases = connection.execute("""
            SELECT vendor,order_ref FROM purchases ORDER BY id
        """).fetchall()
        supplies = connection.execute("""
            SELECT name,kind,purchased_qty,remaining_qty
            FROM supplies ORDER BY id
        """).fetchall()
        audit = connection.execute("""
            SELECT action,before_json,after_json
            FROM change_audit WHERE entity_type='supply' ORDER BY id
        """).fetchall()
        tokens = connection.execute("""
            SELECT COUNT(*) FROM inventory_submissions
            WHERE operation='secondary_supply_intake438'
        """).fetchone()[0]
        categories = connection.execute(
            "SELECT COUNT(*) FROM supply_categories"
        ).fetchone()[0]
    return purchases, supplies, audit, tokens, categories


def test_private_intake_creates_purchase_bucket_audit_and_no_admin_records(browser):
    client, root = browser
    _login(client, 2)
    data = _form(client)
    response = client.post(
        "/secondary/supplies", data=data, follow_redirects=False,
    )
    assert response.status_code == 303
    assert response.headers["location"] == "/secondary/supplies"

    purchases, supplies, audit, tokens, categories = _state(root, 2)
    assert purchases == [
        ("Secondary Supply Intake", "secondary-supply-intake438"),
    ]
    assert supplies == [("PRIVATE-SUPPLY-438", "bac_water", 25.0, 25.0)]
    assert len(audit) == 1
    assert audit[0][0] == "secondary_supply_intake438"
    assert tokens == 1
    assert categories >= 7
    assert _state(root, 3)[1] == []
    assert not (root / "tracker.db").exists()

    page = client.get("/secondary/supplies")
    assert "PRIVATE-SUPPLY-438" in page.text
    assert "25 mL" in page.text
    assert page.headers["cache-control"] == "no-store"
    inventory = client.get("/secondary/inventory")
    assert 'href="/secondary/supplies"' in inventory.text


def test_counted_supplies_use_integer_units_and_share_bucket(browser):
    client, root = browser
    _login(client, 2)
    form = _form(client, kind="needle", quantity="10")
    assert client.post(
        "/secondary/supplies", data=form, follow_redirects=False,
    ).status_code == 303
    second = _form(client, kind="swab", quantity="12")
    assert client.post(
        "/secondary/supplies", data=second, follow_redirects=False,
    ).status_code == 303
    purchases, supplies, _, tokens, _ = _state(root, 2)
    assert len(purchases) == 1
    assert supplies == [
        ("PRIVATE-SUPPLY-438", "needle", 10.0, 10.0),
        ("PRIVATE-SUPPLY-438", "swab", 12.0, 12.0),
    ]
    assert tokens == 2


def test_same_submission_token_is_idempotent_even_with_changed_payload(browser):
    client, root = browser
    _login(client, 2)
    data = _form(client, kind="bac_water", quantity="8")
    assert client.post(
        "/secondary/supplies", data=data, follow_redirects=False,
    ).status_code == 303
    assert client.post("/secondary/supplies", data=data).status_code == 409
    assert client.post(
        "/secondary/supplies", data={**data, "quantity": "9"},
    ).status_code == 409
    assert len(_state(root, 2)[1]) == 1
    assert _state(root, 2)[3] == 1


def test_parallel_same_intake_writes_exactly_one_record(browser):
    _, root = browser
    payload = {
        "name": "CONCURRENT-SUPPLY",
        "kind": "bac_water",
        "quantity": 10.0,
        "notes": "",
        "submission_token": str(uuid4()),
    }
    with ThreadPoolExecutor(max_workers=2) as executor:
        tasks = [
            executor.submit(request_supply438, 2, "create", payload, root)
            for _ in range(2)
        ]
        statuses = [task.result()["status"] for task in tasks]
    assert sorted(statuses) == ["created", "duplicate"]
    assert len(_state(root, 2)[1]) == 1
    assert _state(root, 2)[3] == 1


def test_cross_account_view_and_html_injection_are_isolated(browser):
    client, root = browser
    _login(client, 2)
    data = _form(client)
    data["name"] = '<img src=x onerror="alert(1)">'
    assert client.post(
        "/secondary/supplies", data=data, follow_redirects=False,
    ).status_code == 303
    assert "&lt;img" in client.get("/secondary/supplies").text
    assert '<img src=x onerror=' not in client.get("/secondary/supplies").text

    _login(client, 3)
    page = client.get("/secondary/supplies")
    assert page.status_code == 200
    assert "No supplies recorded yet" in page.text
    assert "&lt;img" not in page.text
    assert _state(root, 3)[1] == []
    assert len(_state(root, 2)[1]) == 1


def test_bad_values_and_forged_fields_never_create_supplies(browser):
    client, root = browser
    _login(client, 2)
    original = _form(client)
    invalid = (
        {"kind": "needle", "quantity": "2.5"},
        {"kind": "wrong"},
        {"quantity": "0"},
        {"quantity": "-1"},
        {"quantity": "NaN"},
        {"quantity": "1000001"},
        {"name": ""},
        {"name": "X" * 161},
        {"user_id": "3"},
        {"database": "/opt/tracker/data/tracker.db"},
        {"sql": "DELETE FROM supplies"},
    )
    for change in invalid:
        response = client.post(
            "/secondary/supplies", data={**original, **change},
        )
        assert response.status_code == 422, (change, response.status_code)
    assert _state(root, 2)[1] == []


def test_csrf_unauthenticated_query_and_disabled_flags(browser, monkeypatch):
    client, root = browser
    assert client.get(
        "/secondary/supplies", follow_redirects=False,
    ).status_code == 303
    assert client.post("/secondary/supplies", data={}).status_code == 401
    _login(client, 2)
    form = _form(client)
    assert client.post(
        "/secondary/supplies", data={**form, "csrf_token": "forged"},
    ).status_code == 403
    assert client.post(
        "/secondary/supplies",
        data=form, headers={"Sec-Fetch-Site": "cross-site"},
    ).status_code == 403
    assert client.post(
        "/secondary/supplies?user_id=3", data=form,
    ).status_code == 400

    monkeypatch.delenv("TRACKER_SECONDARY_SUPPLY_WRITES438", raising=False)
    assert client.get("/secondary/supplies").status_code == 200
    assert 'action="/secondary/supplies"' not in client.get(
        "/secondary/supplies"
    ).text
    assert client.post("/secondary/supplies", data=form).status_code == 404
    assert _state(root, 2)[1] == []
    monkeypatch.setenv("TRACKER_SECONDARY_SUPPLY_WRITES438", "1")
    monkeypatch.setattr(config, "instance_label", lambda: "PROD")
    assert client.get("/secondary/supplies").status_code == 404
    assert client.post("/secondary/supplies", data=form).status_code == 404


@pytest.mark.parametrize("raw", (
    b"",
    b"[]",
    b'{"action":"list","user_id":3}',
    b'{"action":"create","database":"/tmp/admin","payload":{}}',
    b'{"action":"list","action":"list"}',
    b'{"action":"use","payload":{}}',
    b'x' * 4097,
))
def test_worker_rejects_arbitrary_requests(raw):
    with pytest.raises(ValueError):
        parse_request438(raw)


def test_no_admin_worker_access_or_unsupported_ops(browser):
    _, root = browser
    with pytest.raises(PermissionError):
        request_supply438(1, "list", data_root=root)
    with pytest.raises(ValueError):
        request_supply438(2, "use", data_root=root)


def test_main_middleware_only_exempts_gated_supply_post():
    from pathlib import Path
    code = Path("app/main.py").read_text()
    assert 'secondary_preview430.supply_writes_enabled438()' in code
    assert 'request.url.path == "/secondary/supplies"' in code
    assert "and not secondary_form_post433" in code
