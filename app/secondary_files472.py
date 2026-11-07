"""Release 472: DEV-gated private attachments.

Every operation obtains identity from the verified secondary
session. Never accepts a user ID, filesystem path, SQL or URL
from the browser. Writes are disabled unless explicitly opted in.
"""
import hashlib
import os
import re
import secrets
import sqlite3
from contextlib import closing
from datetime import date
from html import escape
from urllib.parse import quote

from fastapi import HTTPException
from sqlalchemy import text

from . import config
from .secondary_attachments471 import (
    MIME471, MAX_BYTES471, _checked_directory471,
)
from .secondary_orm468 import private_orm468
from .secondary_request_db467 import verified_private_scope467

TABLES472 = {"coa": "coas", "labs": "lab_reports"}

def upload_enabled472():
    from .secondary_preview430 import preview_enabled
    return (
        preview_enabled()
        and os.getenv("TRACKER_SECONDARY_ATTACHMENT_UPLOAD472", "0") == "1"
    )

def valid_day472(value):
    if type(value) is not str or len(value) != 10:
        raise ValueError("Invalid report date")
    parsed = date.fromisoformat(value)
    if parsed.isoformat() != value:
        raise ValueError("Invalid report date")
    return value

def detect_mime472(data):
    if data.startswith(b"%PDF-"):
        return "application/pdf"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    raise ValueError("Unsupported attachment content")

def _name472(value):
    if (
        type(value) is not str
        or not 1 <= len(value) <= 255
        or any(ord(c) < 32 for c in value)
        or "/" in value or "\\" in value
    ):
        raise ValueError("Invalid attachment filename")
    return value

def private_catalog472(request):
    with private_orm468(request) as (scope, db):
        entries = []
        for kind, table in TABLES472.items():
            rows = db.execute(text(
                "SELECT id,original_name,content_type,size_bytes "
                f"FROM {table} WHERE stored_name IS NOT NULL "
                "AND original_name IS NOT NULL "
                "ORDER BY id DESC LIMIT 100"
            )).all()
            for rid, name, mime, size in rows:
                if not name or not mime or not size:
                    continue
                entries.append({
                    "kind": kind,
                    "id": rid,
                    "name": str(name)[:255],
                    "mime": str(mime)[:80],
                    "size": size,
                })
    return {"user_id": scope.user_id, "entries": entries}

def render_catalog472(report, token=None):
    if (
        type(report) is not dict
        or type(report.get("user_id")) is not int
        or report["user_id"] <= 1
        or type(report.get("entries")) is not list
        or len(report["entries"]) > 200
    ):
        raise ValueError("Invalid attachment catalog")

    rows = []
    for entry in report["entries"]:
        if (
            type(entry) is not dict
            or set(entry) != {"kind","id","name","mime","size"}
            or entry["kind"] not in TABLES472
            or type(entry["id"]) is not int
            or not 1 <= entry["id"] <= 2147483647
        ):
            raise ValueError("Invalid attachment entry")
        url = (
            "/secondary/attachments/"
            + entry["kind"] + "/" + str(entry["id"])
        )
        rows.append(
            '<li><a href="' + escape(url, quote=True) + '">'
            + escape(entry["name"]) + '</a> · '
            + escape(entry["kind"].upper()) + ' · '
            + escape(str(entry["size"])) + ' bytes</li>'
        )
    entries = "".join(rows) or "<li>No uploaded attachments yet.</li>"
    form = ""
    if token is not None:
        token = escape(token, quote=True)
        form = f'''
<section><h2>Upload a private document</h2>
<form action="/secondary/attachments/upload"
method="post" enctype="multipart/form-data">
<input type="hidden" name="csrf_token" value="{token}">
<label>Document category
<select name="kind" required>
<option value="labs">Lab report</option>
<option value="coa">Certificate of analysis</option>
</select></label>
<label>Lab draw date (required for lab reports)
<input name="drawn_on" type="date"></label>
<label>Lab name
<input name="lab_name" maxlength="160"></label>
<label>File (PDF, PNG, JPEG or WebP; max 15 MB)
<input name="file" type="file"
accept=".pdf,.png,.jpg,.jpeg,.webp" required></label>
<button type="submit">Upload document</button>
</form></section>'''

    return f'''<!doctype html><html lang="en"><head>
<meta charset="utf-8"><meta name="viewport"
content="width=device-width,initial-scale=1">
<meta name="referrer" content="no-referrer">
<title>Private Documents · Tracker DEV</title>
<style>
*{{box-sizing:border-box}}
body{{font:16px/1.5 system-ui,sans-serif;margin:0;
background:#f3f6fa;color:#182333}}
main{{max-width:760px;margin:auto;padding:16px}}
section{{background:white;border:1px solid #ced9e5;
border-radius:12px;padding:16px;margin:12px 0}}
li{{margin:12px 0;overflow-wrap:anywhere}}
label{{display:grid;gap:6px;margin:14px 0}}
input,select,button{{font:inherit;min-height:44px;
padding:8px;width:100%;max-width:100%}}
button{{background:#16558b;color:white;border:0;
border-radius:8px}}
a{{color:#16558b}}
</style></head><body><main>
<nav><a href="/secondary/overview">Workspace</a> ·
<a href="/secondary/orm-summary">Summary</a></nav>
<h1>Private Documents</h1>
<p>Account {report["user_id"]} · DEV-only private storage</p>
<section><h2>COAs and Lab Reports</h2>
<ul>{entries}</ul></section>{form}
<p>Downloads are verified against the stored SHA-256 digest.
Normal multi-user login is not enabled.</p>
</main></body></html>'''

def _save_exclusive472(directory, filename, data):
    fd = None
    try:
        dirfd = os.open(
            directory, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
        )
        try:
            fd = os.open(
                filename, os.O_CREAT | os.O_EXCL | os.O_WRONLY
                | os.O_NOFOLLOW, 0o600, dir_fd=dirfd
            )
            with os.fdopen(fd, "wb") as output:
                fd = None
                output.write(data)
                output.flush()
                os.fsync(output.fileno())
        finally:
            if fd is not None:
                os.close(fd)
            os.close(dirfd)
    except OSError:
        raise HTTPException(503, "Private attachment storage unavailable") from None

def private_upload472(request, kind, filename, data, drawn_on, lab_name):
    from .secondary_preview430 import COOKIE, _session_user

    if not upload_enabled472():
        raise HTTPException(404, "Private uploads disabled")
    if kind not in TABLES472:
        raise HTTPException(422, "Invalid document category")
    name = _name472(filename)
    if type(lab_name) is not str or len(lab_name) > 160:
        raise HTTPException(422, "Invalid lab name")
    if type(data) is not bytes or not 0 < len(data) <= MAX_BYTES471:
        raise HTTPException(413, "Invalid attachment size")
    try:
        mime = detect_mime472(data)
        day = valid_day472(drawn_on) if kind == "labs" else None
    except ValueError:
        raise HTTPException(422, "Invalid attachment type or date") from None

    scope = verified_private_scope467(request)
    directory = _checked_directory471(scope, kind)
    extension = MIME471[mime]
    stored = secrets.token_hex(24) + "." + extension
    digest = hashlib.sha256(data).hexdigest()

    _save_exclusive472(directory, stored, data)
    committed = False
    record_id = None

    try:
        uri = (
            "file:" + quote(str(scope.database), safe="/")
            + "?mode=rw"
        )
        with closing(sqlite3.connect(
            uri, uri=True, timeout=10
        )) as db:
            db.execute("PRAGMA foreign_keys=ON")
            db.execute("BEGIN IMMEDIATE")
            marker = db.execute("""
                SELECT user_id,status,schema_version
                FROM tracker_staged_workspace426
            """).fetchall()

            if marker != [(scope.user_id, "inactive", 426)]:
                raise RuntimeError("Workspace identity mismatch")

            # Revalidate the current session immediately
            # before the database mutation.
            if _session_user(request.cookies.get(COOKIE)) != scope.user_id:
                raise PermissionError("Secondary session revoked")

            if kind == "labs":
                result = db.execute("""
                    INSERT INTO lab_reports
                    (drawn_on,lab_name,notes,original_name,
                     stored_name,content_type,size_bytes,sha256)
                    VALUES (?,?,?,?,?,?,?,?)
                """, (
                    day, lab_name.strip(), "", name,
                    stored, mime, len(data), digest,
                ))
            else:
                # Raw SQLite bypasses SQLAlchemy's Python-side
                # defaults. Supply every required text value.
                result = db.execute("""
                    INSERT INTO coas
                    (original_name,stored_name,content_type,
                     size_bytes,sha256,lab_name,notes,
                     job_id,verify_code,
                     verification_status,verification_notes)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?)
                """, (
                    name, stored, mime, len(data), digest,
                    lab_name.strip(), "", "", "",
                    "unreviewed", "",
                ))
            record_id = result.lastrowid
            db.commit()
            committed = True
    except (sqlite3.Error, RuntimeError, PermissionError, OSError):
        raise HTTPException(503, "Private attachment upload failed") from None
    finally:
        if not committed:
            # Only unlink the randomly generated file owned
            # by this failed transaction.
            (directory / stored).unlink(missing_ok=True)

    return kind, record_id
