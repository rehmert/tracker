"""Release 437 reconciliation conflict tests independently scheduled by loadfile."""

import json
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from uuid import uuid4

import pytest

from app import config
from app.worker_reconciliation437 import parse_request437, request_reconciliation437
from scripts.secondary_reconciliation437_support import browser, _login, _form, _db, _state

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
