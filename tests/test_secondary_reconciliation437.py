"""Release 437 reconciliation tests, sharded by independent workspace fixture."""

import json
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from uuid import uuid4

import pytest

from app import config
from app.worker_reconciliation437 import parse_request437, request_reconciliation437
from scripts.secondary_reconciliation437_support import browser, _login, _form, _db, _state

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
