"""Release 489: gated private vial creation from primary Tracker preview."""

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
def browser489(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(config, "instance_label", lambda: "DEV")
    monkeypatch.setenv("TRACKER_SECONDARY_PREVIEW430", "1")
    monkeypatch.setenv("TRACKER_SECONDARY_INVENTORY_WRITES435", "1")
    monkeypatch.setenv("TRACKER_FULLAPP_GATEWAY486", "1")
    monkeypatch.setenv("TRACKER_FULLAPP_WRITES488", "1")
    monkeypatch.setenv("TRACKER_FULLAPP_VIAL_WRITES489", "1")
    monkeypatch.setenv("TRACKER_SECONDARY_LOCKDOWN440", "0")

    auth.bootstrap("admin489", "secure-admin-password-489")
    (tmp_path / auth.FLAG).write_text("DEV enabled")

    for uid in (2, 3):
        initialize_staged_workspace426(uid, tmp_path)
        stage_secondary_account427(
            uid, f"member-{uid}", f"secondary-password-{uid}-secure-489"
        )

    for uid, cid in ((2, 1), (3, 9)):
        with sqlite3.connect(
            tmp_path / "users" / str(uid) / "tracker.db"
        ) as db:
            db.execute("""
                INSERT INTO compounds
                    (id,name,category,notes,primary_unit)
                VALUES (?,?,?,?,?)
            """, (cid, f"compound-user-{uid}-489", "peptide", "", "mg"))

    host = FastAPI()
    host.mount("/secondary", preview_app)
    with TestClient(host, base_url="https://tracker.test") as client:
        yield client, tmp_path


def _hidden(html, key):
    match = re.search(
        rf'name="{re.escape(key)}"\s+value="([^"]+)"',
        html,
    )
    assert match is not None, f"Missing hidden field {key}"
    return match.group(1)


def _login(client, uid):
    page = client.get("/secondary/login")
    assert page.status_code == 200
    result = client.post(
        "/secondary/login",
        data={
            "username": f"member-{uid}",
            "password": f"secondary-password-{uid}-secure-489",
            "csrf_token": _hidden(page.text, "csrf_token"),
        },
        follow_redirects=False,
    )
    assert result.status_code == 303


def _vial_form(page, cid, label):
    assert page.status_code == 200, page.text[-800:]
    assert 'action="/secondary/full/vials"' in page.text
    return {
        "compound_id": str(cid),
        "label": label,
        "content_value": "10",
        "content_unit": "mg",
        "form": "lyophilized",
        "volume_ml": "",
        "lot": "PRIVATE-489",
        "cap_color": "Blue",
        "notes": "isolated vial from primary preview",
        "csrf_token": _hidden(page.text, "csrf_token"),
        "submission_token": _hidden(page.text, "submission_token"),
    }


def _vials(root, uid):
    path = root / "users" / str(uid) / "tracker.db"
    with sqlite3.connect(path) as db:
        return db.execute("""
            SELECT compound_id,label,content_value,content_unit,
                   form,volume_ml,status,notes
            FROM vials ORDER BY id
        """).fetchall()


def test_vial_form_creates_only_for_authenticated_user(browser489):
    client, root = browser489
    _login(client, 2)

    page = client.get("/secondary/full/vials")
    assert page.status_code == 200
    assert "compound-user-2-489" in page.text
    assert "compound-user-3-489" not in page.text
    assert 'option value="1"' in page.text
    assert 'option value="9"' not in page.text
    assert "form-action 'self'" in page.headers["content-security-policy"]

    valid = _vial_form(page, 1, "user-two-vial-489")
    result = client.post(
        "/secondary/full/vials", data=valid, follow_redirects=False
    )
    assert result.status_code == 303, result.text[-800:]
    assert result.headers["location"] == "/secondary/full/vials"
    assert _vials(root, 2) == [
        (1, "user-two-vial-489", 10.0, "mg", "lyophilized",
         None, "sealed", "isolated vial from primary preview"),
    ]
    assert _vials(root, 3) == []
    assert not (root / "tracker.db").exists()

    follow = client.get("/secondary/full/vials")
    assert follow.status_code == 200
    assert "user-two-vial-489" in follow.text

    _login(client, 3)
    second = client.get("/secondary/full/vials")
    assert "user-two-vial-489" not in second.text
    assert 'option value="9"' in second.text
    assert 'option value="1"' not in second.text

    result = client.post(
        "/secondary/full/vials",
        data=_vial_form(second, 9, "user-three-vial-489"),
        follow_redirects=False,
    )
    assert result.status_code == 303
    assert len(_vials(root, 2)) == len(_vials(root, 3)) == 1
    assert _vials(root, 3)[0][1] == "user-three-vial-489"


def test_vial_csrf_replay_and_duplicate_are_rejected(browser489):
    client, root = browser489
    assert client.post(
        "/secondary/full/vials", data={"label": "anonymous"}
    ).status_code == 401

    _login(client, 2)
    valid = _vial_form(
        client.get("/secondary/full/vials"), 1, "once-only-489"
    )
    assert client.post(
        "/secondary/full/vials",
        data={**valid, "csrf_token": "forged"},
    ).status_code == 403
    assert client.post(
        "/secondary/full/vials",
        data=valid,
        headers={"Sec-Fetch-Site": "cross-site"},
    ).status_code == 403
    assert _vials(root, 2) == []

    assert client.post(
        "/secondary/full/vials", data=valid, follow_redirects=False
    ).status_code == 303
    assert client.post(
        "/secondary/full/vials", data=valid
    ).status_code == 409
    assert client.post(
        "/secondary/full/vials",
        data={**valid, "label": "changed-after-replay"},
    ).status_code == 409
    assert len(_vials(root, 2)) == 1


def test_form_denies_forged_user_and_foreign_compound(browser489):
    client, root = browser489
    _login(client, 2)
    valid = _vial_form(
        client.get("/secondary/full/vials"), 1, "safe-489"
    )

    assert client.post(
        "/secondary/full/vials?user_id=3",
        data=valid,
    ).status_code == 400

    assert client.post(
        "/secondary/full/vials",
        data={**valid, "user_id": "3"},
    ).status_code == 422

    # User 3 owns compound 9. User 2 cannot reference it.
    assert client.post(
        "/secondary/full/vials",
        data={**valid, "compound_id": "9"},
    ).status_code == 422

    assert client.post(
        "/secondary/full/vials",
        data={**valid, "form": "solution", "volume_ml": ""},
    ).status_code == 422

    assert _vials(root, 2) == []
    assert _vials(root, 3) == []


def test_write_flags_disable_form_and_post(browser489, monkeypatch):
    client, root = browser489
    _login(client, 2)

    for key in (
        "TRACKER_FULLAPP_VIAL_WRITES489",
        "TRACKER_FULLAPP_WRITES488",
        "TRACKER_SECONDARY_INVENTORY_WRITES435",
    ):
        monkeypatch.setenv(key, "0")
        page = client.get("/secondary/full/vials")
        assert page.status_code == 200
        assert 'action="/secondary/full/vials"' not in page.text
        assert "form-action 'none'" in page.headers["content-security-policy"]
        assert client.post(
            "/secondary/full/vials",
            data={"label": "DISABLED"},
        ).status_code == 404
        monkeypatch.setenv(key, "1")

    monkeypatch.setattr(config, "instance_label", lambda: "PROD")
    assert client.post(
        "/secondary/full/vials",
        data={"label": "DISABLED"},
    ).status_code == 404
    assert _vials(root, 2) == []


def test_main_middleware_has_exact_path_and_all_four_gates():
    from pathlib import Path
    main = Path("app/main.py").read_text()
    assert 'os.environ.get("TRACKER_FULLAPP_GATEWAY486", "0") == "1"' in main
    assert 'os.environ.get("TRACKER_FULLAPP_WRITES488", "0") == "1"' in main
    assert 'os.environ.get("TRACKER_FULLAPP_VIAL_WRITES489", "0") == "1"' in main
    assert "secondary_preview430.inventory_writes_enabled435()" in main
    assert 'request.url.path == "/secondary/full/vials"' in main
