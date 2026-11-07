"""Release 488: first interactive private primary-page write, reuse 435."""

import re
import sqlite3

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app import config, session_auth385 as auth
from app.secondary_preview430 import preview_app
from app.user_accounts427 import stage_secondary_account427
from app.user_bootstrap426 import initialize_staged_workspace426


@pytest.fixture
def browser488(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(config, "instance_label", lambda: "DEV")
    monkeypatch.setenv("TRACKER_SECONDARY_PREVIEW430", "1")
    monkeypatch.setenv("TRACKER_SECONDARY_INVENTORY_WRITES435", "1")
    monkeypatch.setenv("TRACKER_FULLAPP_GATEWAY486", "1")
    monkeypatch.setenv("TRACKER_FULLAPP_WRITES488", "1")
    monkeypatch.setenv("TRACKER_SECONDARY_LOCKDOWN440", "0")

    auth.bootstrap("admin488", "secure-admin-password-488")
    (tmp_path / auth.FLAG).write_text("DEV enabled")

    for uid in (2, 3):
        initialize_staged_workspace426(uid, tmp_path)
        stage_secondary_account427(
            uid, f"member-{uid}", f"secondary-password-{uid}-secure-488",
        )

    host = FastAPI()
    host.mount("/secondary", preview_app)
    with TestClient(host, base_url="https://tracker.test") as client:
        yield client, tmp_path


def _hidden(html, key):
    match = re.search(
        rf'name="{re.escape(key)}"\s+value="([^"]+)"', html
    )
    assert match is not None
    return match.group(1)


def _login(client, uid):
    login = client.get("/secondary/login")
    assert login.status_code == 200
    response = client.post(
        "/secondary/login",
        data={
            "username": f"member-{uid}",
            "password": f"secondary-password-{uid}-secure-488",
            "csrf_token": _hidden(login.text, "csrf_token"),
        },
        follow_redirects=False,
    )
    assert response.status_code == 303


def _private_compounds(root, uid):
    with sqlite3.connect(root / "users" / str(uid) / "tracker.db") as db:
        return db.execute(
            "SELECT name,category,primary_unit,notes "
            "FROM compounds ORDER BY id"
        ).fetchall()


def _payload(page, name):
    assert 'action="/secondary/full/compounds"' in page.text
    return {
        "name": name,
        "category": "peptide",
        "primary_unit": "mg",
        "notes": "isolated private compound",
        "csrf_token": _hidden(page.text, "csrf_token"),
        "submission_token": _hidden(page.text, "submission_token"),
    }


def test_primary_compound_page_creates_only_for_signed_in_user(browser488):
    client, root = browser488
    _login(client, 2)

    page = client.get("/secondary/full/compounds")
    assert page.status_code == 200
    assert "form-action 'self'" in page.headers["content-security-policy"]
    assert "secure" in page.headers["set-cookie"].lower()
    form = _payload(page, "USER-TWO-488")

    result = client.post(
        "/secondary/full/compounds",
        data=form, follow_redirects=False,
    )
    assert result.status_code == 303, result.text[:1000]
    assert result.headers["location"] == "/secondary/full/compounds"

    assert _private_compounds(root, 2) == [
        ("USER-TWO-488", "peptide", "mg", "isolated private compound"),
    ]
    assert _private_compounds(root, 3) == []
    assert not (root / "tracker.db").exists()

    reread = client.get("/secondary/full/compounds")
    assert reread.status_code == 200
    assert "USER-TWO-488" in reread.text

    _login(client, 3)
    second = client.get("/secondary/full/compounds")
    assert second.status_code == 200
    assert "USER-TWO-488" not in second.text
    second_form = _payload(second, "USER-THREE-488")
    assert client.post(
        "/secondary/full/compounds",
        data=second_form, follow_redirects=False,
    ).status_code == 303

    assert _private_compounds(root, 3)[0][0] == "USER-THREE-488"
    assert len(_private_compounds(root, 2)) == 1


def test_compound_write_requires_signed_csrf_and_idempotency(browser488):
    client, root = browser488

    # Pre-authentication no handler may authorize private writes.
    anonymous = client.post(
        "/secondary/full/compounds",
        data={"name": "ANONYMOUS"},
    )
    assert anonymous.status_code == 401

    _login(client, 2)
    page = client.get("/secondary/full/compounds")
    valid = _payload(page, "ONE-RECORD-488")

    assert client.post(
        "/secondary/full/compounds",
        data={**valid, "csrf_token": "forged"},
    ).status_code == 403

    assert client.post(
        "/secondary/full/compounds",
        data=valid, headers={"Sec-Fetch-Site": "cross-site"},
    ).status_code == 403

    assert client.post(
        "/secondary/full/compounds",
        data=valid, follow_redirects=False,
    ).status_code == 303

    assert client.post(
        "/secondary/full/compounds",
        data=valid,
    ).status_code == 409
    assert client.post(
        "/secondary/full/compounds",
        data={**valid, "name": "REPLAYED"},
    ).status_code == 409

    assert _private_compounds(root, 2)[0][0] == "ONE-RECORD-488"
    assert len(_private_compounds(root, 2)) == 1


def test_disabled_flag_and_prod_fail_closed(browser488, monkeypatch):
    client, root = browser488
    _login(client, 2)

    monkeypatch.setenv("TRACKER_FULLAPP_WRITES488", "0")
    page = client.get("/secondary/full/compounds")
    assert page.status_code == 200
    assert 'action="/secondary/full/compounds"' not in page.text
    assert "form-action 'none'" in page.headers["content-security-policy"]
    assert client.post(
        "/secondary/full/compounds",
        data={"name": "DISABLED"},
    ).status_code == 404

    monkeypatch.setenv("TRACKER_FULLAPP_WRITES488", "1")
    monkeypatch.setenv("TRACKER_SECONDARY_INVENTORY_WRITES435", "0")
    assert client.post(
        "/secondary/full/compounds",
        data={"name": "DISABLED"},
    ).status_code == 404

    monkeypatch.setenv("TRACKER_SECONDARY_INVENTORY_WRITES435", "1")
    monkeypatch.setattr(config, "instance_label", lambda: "PROD")
    assert client.post(
        "/secondary/full/compounds",
        data={"name": "DISABLED"},
    ).status_code == 404
    assert _private_compounds(root, 2) == []


def test_unexpected_params_rejected_and_admin_not_selected(browser488):
    client, root = browser488
    _login(client, 2)

    form = _payload(client.get("/secondary/full/compounds"), "SAFE-488")
    assert client.post(
        "/secondary/full/compounds?user_id=3",
        data=form,
    ).status_code == 400

    assert client.post(
        "/secondary/full/compounds",
        data={**form, "user_id": "3"},
    ).status_code == 422

    assert _private_compounds(root, 2) == []
    assert _private_compounds(root, 3) == []


def test_main_application_csrf_exemption_stays_conditional():
    from pathlib import Path
    main = Path("app/main.py").read_text()
    assert 'os.environ.get("TRACKER_FULLAPP_WRITES488", "0") == "1"' in main
    assert "secondary_preview430.inventory_writes_enabled435()" in main
    assert 'request.url.path == "/secondary/full/compounds"' in main
