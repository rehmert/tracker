"""Release 487: real DEV secondary-session -> private snapshot -> primary route."""

import hashlib
import re
import sqlite3
import subprocess
import sys

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app import config, session_auth385 as auth
from app.secondary_preview430 import COOKIE, preview_app
from app.user_accounts427 import stage_secondary_account427
from app.user_bootstrap426 import initialize_staged_workspace426
from app.worker_scope428 import SOURCE_ROOT, worker_environment428


@pytest.fixture
def private_clients(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(config, "instance_label", lambda: "DEV")
    monkeypatch.setenv("TRACKER_SECONDARY_PREVIEW430", "1")
    monkeypatch.setenv("TRACKER_FULLAPP_GATEWAY486", "1")
    monkeypatch.setenv("TRACKER_SECONDARY_LOCKDOWN440", "0")

    auth.bootstrap("admin487", "private-credentials-for-admin-487")
    (tmp_path / auth.FLAG).write_text("DEV enabled")

    for uid in (2, 3):
        initialize_staged_workspace426(uid, tmp_path)
        stage_secondary_account427(
            uid, f"member-{uid}",
            f"secondary-password-{uid}-secure-487",
        )

    with sqlite3.connect(tmp_path / "users" / "2" / "tracker.db") as db:
        db.execute("""
            INSERT INTO compounds (name,category,notes,primary_unit)
            VALUES ('private-487-two','other','','mg')
        """)

    with sqlite3.connect(tmp_path / "users" / "3" / "tracker.db") as db:
        db.execute("""
            INSERT INTO compounds (name,category,notes,primary_unit)
            VALUES ('private-487-three','other','','mg')
        """)

    host = FastAPI()
    host.mount("/secondary", preview_app)
    with TestClient(host, base_url="https://tracker.test") as client:
        yield client, tmp_path


def login(client, uid):
    page = client.get("/secondary/login")
    assert page.status_code == 200
    match = re.search(
        r'name="csrf_token"\s+value="([^"]+)"',
        page.text,
    )
    assert match is not None
    signed = client.post(
        "/secondary/login",
        data={
            "username": f"member-{uid}",
            "password": f"secondary-password-{uid}-secure-487",
            "csrf_token": match.group(1),
        },
        follow_redirects=False,
    )
    assert signed.status_code == 303
    assert client.cookies.get(COOKIE)


def counts(root):
    results = []
    for uid in (2, 3):
        path = root / "users" / str(uid) / "tracker.db"
        with sqlite3.connect(path) as db:
            results.append(db.execute(
                "SELECT COUNT(*) FROM compounds"
            ).fetchone()[0])
    return results


def logical_private_digest491(path):
    """Compare actual SQLite content, not file bytes.

    SQLite can legitimately rewrite headers/pages when WAL checkpoints
    complete, even if the application's logical data is unchanged.
    Reading from a read-only connection avoids creating a new database.
    """
    with sqlite3.connect("file:" + str(path) + "?mode=ro", uri=True) as db:
        db.execute("PRAGMA query_only=ON")
        logical_dump = "\n".join(db.iterdump())
    return hashlib.sha256(logical_dump.encode("utf-8")).digest()


def test_private_primary_page_from_isolated_snapshot(private_clients):
    client, root = private_clients
    original_counts = counts(root)
    db_two = root / "users" / "2" / "tracker.db"
    original_hash = logical_private_digest491(db_two)

    login(client, 2)
    result = client.get("/secondary/full/compounds")
    assert result.status_code == 200, result.text[-1500:]
    assert "private-487-two" in result.text
    assert "private-487-three" not in result.text
    assert "<form" not in result.text
    assert "<script" not in result.text
    assert "default-src 'none'" in result.headers["content-security-policy"]
    assert result.headers["cache-control"] == "no-store"

    login(client, 3)
    second = client.get("/secondary/full/compounds")
    assert second.status_code == 200, second.text[-1500:]
    assert "private-487-three" in second.text
    assert "private-487-two" not in second.text

    assert counts(root) == original_counts == [1, 1]
    assert logical_private_digest491(db_two) == original_hash


def test_unauthorized_cannot_launch_private_worker(private_clients, monkeypatch):
    client, root = private_clients
    import app.secondary_fullapp487 as module

    def refuse_launch(*args, **kwargs):
        raise AssertionError("Unauthorized request tried to spawn worker")

    monkeypatch.setattr(module.subprocess, "run", refuse_launch)
    assert client.get("/secondary/full/compounds").status_code == 401

    login(client, 2)
    # Release 488 registers a POST route, but the independent write gate
    # defaults off. It must deny without starting any private worker.
    monkeypatch.setenv("TRACKER_FULLAPP_WRITES488", "0")
    assert client.post("/secondary/full/compounds").status_code == 404

    monkeypatch.setenv("TRACKER_SECONDARY_LOCKDOWN440", "1")
    assert client.get("/secondary/full/compounds").status_code == 404
    monkeypatch.setenv("TRACKER_SECONDARY_LOCKDOWN440", "0")

    monkeypatch.setenv("TRACKER_FULLAPP_GATEWAY486", "0")
    assert client.get("/secondary/full/compounds").status_code == 404


def test_bad_workspace_identity_stops_before_worker(private_clients, monkeypatch):
    client, root = private_clients
    login(client, 2)

    with sqlite3.connect(root / "users" / "2" / "tracker.db") as db:
        db.execute("""
            UPDATE tracker_staged_workspace426 SET user_id=3
        """)

    import app.secondary_fullapp487 as module
    monkeypatch.setattr(
        module.subprocess, "run",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("Invalid workspace launched")
        ),
    )
    assert client.get("/secondary/full/compounds").status_code == 401


def test_browser_cannot_select_other_workspace(private_clients):
    client, root = private_clients
    login(client, 2)
    assert client.get(
        "/secondary/full/compounds?user_id=3"
    ).status_code == 400
    assert client.get(
        "/secondary/full/compounds?q=x&uid=3"
    ).status_code == 400
    assert client.get(
        "/secondary/full/compounds?q=a&q=b"
    ).status_code == 400


def test_injection_rejected_before_app_import(private_clients):
    _, root = private_clients
    environment = worker_environment428(2, root)
    for payload in (
        b'{"route":"/compounds","query":{},"user_id":3}',
        b'{"route":"/account/users","query":{}}',
        b'{"route":"/compounds","query":{},"route":"/vitals"}',
        b'{"route":"/food","query":{"database":"/etc/passwd"}}',
    ):
        result = subprocess.run(
            [sys.executable, "-m", "app.worker_page487"],
            cwd=SOURCE_ROOT,
            env=environment,
            input=payload,
            capture_output=True,
            timeout=20,
        )
        assert result.returncode != 0
        assert not result.stdout.strip()


def test_prod_and_disabled_flag_cannot_forward(private_clients, monkeypatch):
    client, root = private_clients
    login(client, 2)
    monkeypatch.setattr(config, "instance_label", lambda: "PROD")
    assert client.get("/secondary/full/compounds").status_code == 404
