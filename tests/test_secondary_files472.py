"""Release 472 end-to-end private file tests."""
import hashlib
import re
import sqlite3
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app import config, session_auth385 as auth
from app.secondary_preview430 import preview_app, COOKIE
from app.user_bootstrap426 import initialize_staged_workspace426
from app.user_accounts427 import stage_secondary_account427
from app.secondary_files472 import detect_mime472
from app.secondary_backup472 import backup_secondary472


@pytest.fixture
def browser(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(config, "instance_label", lambda: "DEV")
    monkeypatch.setenv("TRACKER_SECONDARY_PREVIEW430", "1")
    monkeypatch.setenv("TRACKER_SECONDARY_ATTACHMENT_UPLOAD472", "1")
    monkeypatch.delenv("TRACKER_SECONDARY_LOCKDOWN440", raising=False)
    auth.bootstrap("operator", "admin-private-files-472-secure")
    (tmp_path / auth.FLAG).write_text("enabled")
    for uid in (2, 3):
        initialize_staged_workspace426(uid, tmp_path)
        stage_secondary_account427(
            uid, f"member-{uid}", f"member-{uid}-secure-password-472",
        )
    host = FastAPI()
    host.mount("/secondary", preview_app)
    with TestClient(host, base_url="https://tracker.test") as client:
        yield client, tmp_path


def login(client, uid):
    page = client.get("/secondary/login")
    token = re.search(
        r'name="csrf_token"\s+value="([^"]+)"', page.text
    ).group(1)
    response = client.post(
        "/secondary/login",
        data={
            "username": f"member-{uid}",
            "password": f"member-{uid}-secure-password-472",
            "csrf_token": token,
        },
        follow_redirects=False,
    )
    assert response.status_code == 303


def upload(client, kind, data):
    page = client.get("/secondary/attachments")
    assert page.status_code == 200
    token = re.search(
        r'name="csrf_token"\s+value="([^"]+)"', page.text
    ).group(1)
    return client.post(
        "/secondary/attachments/upload",
        data={
            "kind": kind,
            "drawn_on": "2026-11-07",
            "lab_name": "Test laboratory",
            "csrf_token": token,
        },
        files={"file": ("my-report.pdf", data, "application/pdf")},
        follow_redirects=False,
    )


def test_472_upload_catalog_download_and_isolation(browser):
    client, root = browser
    payload2 = b"%PDF-1.4\naccount-two\n%%EOF\n"
    payload3 = b"%PDF-1.4\naccount-three\n%%EOF\n"

    assert client.get(
        "/secondary/attachments", follow_redirects=False
    ).status_code == 303

    login(client, 2)
    for kind in ("coa", "labs"):
        created = upload(client, kind, payload2)
        assert created.status_code == 303
        url = created.headers["location"]
        assert url.startswith(
            "/secondary/attachments/" + kind + "/"
        )
        download = client.get(url)
        assert download.status_code == 200
        assert download.content == payload2

    catalog = client.get("/secondary/attachments")
    assert catalog.status_code == 200
    assert catalog.text.count("my-report.pdf") == 2
    assert "/secondary/attachments/coa/1" in catalog.text
    assert "/secondary/attachments/labs/1" in catalog.text

    for kind in ("coa", "labs"):
        dbpath = root / "users" / "2" / "tracker.db"
        table = "coas" if kind == "coa" else "lab_reports"
        with sqlite3.connect(dbpath) as db:
            row = db.execute(
                f"SELECT sha256,size_bytes FROM {table} WHERE id=1"
            ).fetchone()
        assert row == (
            hashlib.sha256(payload2).hexdigest(),
            len(payload2),
        )

    login(client, 3)
    assert "my-report.pdf" not in client.get(
        "/secondary/attachments"
    ).text

    for kind in ("coa", "labs"):
        created = upload(client, kind, payload3)
        assert created.status_code == 303
        assert client.get(
            "/secondary/attachments/" + kind + "/1"
        ).content == payload3

    assert client.get(
        "/secondary/attachments/coa/1?user_id=2"
    ).status_code == 400


def test_472_rejects_invalid_and_disabled_uploads(browser, monkeypatch):
    client, root = browser
    login(client, 2)

    assert upload(
        client, "coa", b"not-an-image-or-pdf"
    ).status_code == 422
    assert upload(
        client, "backup", b"%PDF-1.4\nhello"
    ).status_code == 422

    with sqlite3.connect(root / "users" / "2" / "tracker.db") as db:
        assert db.execute(
            "SELECT COUNT(*) FROM coas"
        ).fetchone()[0] == 0

    monkeypatch.setenv(
        "TRACKER_SECONDARY_ATTACHMENT_UPLOAD472", "0"
    )
    assert client.get(
        "/secondary/attachments"
    ).status_code == 200
    assert client.post(
        "/secondary/attachments/upload"
    ).status_code == 404

    monkeypatch.setenv(
        "TRACKER_SECONDARY_ATTACHMENT_UPLOAD472", "1"
    )
    monkeypatch.setenv(
        "TRACKER_SECONDARY_LOCKDOWN440", "1"
    )
    assert client.get(
        "/secondary/attachments"
    ).status_code == 404


def test_472_backup_private_and_verified(browser):
    client, root = browser
    login(client, 2)

    result = backup_secondary472(2)
    assert result["user_id"] == 2
    assert result["status"] == "verified"

    saved = (
        root / "users" / "2" / "backups"
        / result["filename"]
    )
    assert saved.is_file()
    assert saved.stat().st_mode & 0o077 == 0

    with sqlite3.connect(saved) as db:
        assert db.execute("""
            SELECT user_id,status,schema_version
            FROM tracker_staged_workspace426
        """).fetchall() == [(2, "inactive", 426)]

    assert not list(
        (root / "users" / "3" / "backups").glob("*.sqlite3")
    )

    with pytest.raises(PermissionError):
        backup_secondary472(1)


def test_472_mime_validation():
    assert detect_mime472(b"%PDF-1.4 test") == "application/pdf"
    assert detect_mime472(b"\x89PNG\r\n\x1a\nstuff") == "image/png"
    with pytest.raises(ValueError):
        detect_mime472(b"definitely not a document")


def test_472_middleware_and_route_contract():
    from app.secondary_preview430 import preview_app
    source = Path("app/main.py").read_text()
    assert "secondary_preview430.upload_enabled472()" in source
    assert '"/secondary/attachments/upload"' in source

    expected = {
        "/attachments": {"GET"},
        "/attachments/upload": {"POST"},
    }
    for path, methods in expected.items():
        matches = [
            r for r in preview_app.routes
            if getattr(r, "path", "") == path
        ]
        assert len(matches) == 1
        assert matches[0].methods == methods


def test_472_coa_sql_satisfies_staged_schema(browser):
    """Verify all required COA columns have SQL values.

    SQLAlchemy Python defaults do not apply to the direct
    SQLite INSERT used by private_upload472.
    """
    import sqlite3
    from pathlib import Path
    import ast

    client, root = browser
    database = root / "users" / "2" / "tracker.db"

    with sqlite3.connect(database) as db:
        columns = db.execute(
            "PRAGMA table_info(coas)"
        ).fetchall()

    required = {
        name
        for _, name, _, not_null, default, pk
        in columns
        if not_null and default is None and not pk
    }

    source = Path(
        "app/secondary_files472.py"
    ).read_text()

    tree = ast.parse(source)

    fn = next(
        node for node in tree.body
        if isinstance(node, ast.FunctionDef)
        and node.name == "private_upload472"
    )

    inserts = []

    for node in ast.walk(fn):
        if (
            isinstance(node, ast.Constant)
            and isinstance(node.value, str)
            and "INSERT INTO coas" in node.value
        ):
            inserts.append(node.value)

    assert len(inserts) == 1

    sql = inserts[0]
    columns_part = sql.split(
        "INSERT INTO coas", 1
    )[1].split("VALUES", 1)[0]

    listed = {
        name.strip()
        for name in columns_part.strip()
            .strip("()").split(",")
    }

    assert required <= listed, (
        "Unspecified required COA columns: "
        + ", ".join(sorted(required - listed))
    )

    assert "job_id" in listed
    assert "verify_code" in listed

    markers = sql.count("?")
    assert markers == len(listed)

    print(
        "Verified COA required columns:",
        sorted(required),
    )
