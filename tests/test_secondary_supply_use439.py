"""Release 439 supply-use worker tests, sharded by independent workspace fixture."""

import json
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import pytest

from app import config
from app.worker_supply_use439 import parse_request439, request_use439
from scripts.secondary_supply_use439_support import browser, _login, _form, _state

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
