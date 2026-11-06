"""DEV-only, explicitly enabled secondary-user gateway and controls.

This is not an application router or a general HTTP proxy.
Staged user credentials remain disabled for normal Tracker login.
"""

import hashlib
import hmac
import os
import secrets
import sqlite3
import time
from contextlib import closing
from html import escape

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from . import config, session_auth385 as auth
from .csrf_runtime import load_key
from .csrf_tokens import issue_token, verify_pair
from .user_accounts427 import (
    inspect_staged_account427,
    staging_environment,
    validate_username,
)
from .worker_request429 import read_workspace_overview429

COOKIE = "tracker_secondary_preview430"
CSRF_COOKIE = "tracker_secondary_csrf430"
LIFETIME = 30 * 60
WINDOW = 15 * 60

preview_app = FastAPI(
    title="Tracker Secondary Preview",
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)


def preview_enabled():
    return (
        config.instance_label() == "DEV"
        and auth.enabled()
        and os.getenv("TRACKER_SECONDARY_PREVIEW430", "0") == "1"
        and os.getenv("TRACKER_SECONDARY_LOCKDOWN440", "0") != "1"
    )


def require_preview():
    if not preview_enabled():
        raise HTTPException(404, "Secondary preview unavailable")
    try:
        staging_environment()
    except (PermissionError, ValueError, RuntimeError, OSError):
        raise HTTPException(503, "Secondary preview unavailable") from None


def _tables(db):
    db.execute("""
        CREATE TABLE IF NOT EXISTS tracker_secondary_sessions430 (
            token_hash TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id),
            expires_at INTEGER NOT NULL
        )
    """)
    db.execute("""
        CREATE TABLE IF NOT EXISTS tracker_secondary_failures430 (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            occurred_at INTEGER NOT NULL
        )
    """)
    db.execute("""
        CREATE INDEX IF NOT EXISTS tracker_secondary_failures_time430
        ON tracker_secondary_failures430(occurred_at)
    """)
    db.commit()


def _verify_credentials(username, password):
    try:
        username = validate_username(username)
    except ValueError:
        return None

    if not isinstance(password, str) or not 12 <= len(password) <= 1024:
        return None

    now = int(time.time())
    with closing(auth.connect()) as db:
        _tables(db)
        db.execute("BEGIN IMMEDIATE")
        db.execute(
            "DELETE FROM tracker_secondary_failures430 WHERE occurred_at < ?",
            (now - WINDOW,),
        )
        attempts = db.execute("""
            SELECT COUNT(*) FROM tracker_secondary_failures430
            WHERE occurred_at>=?
        """, (now - WINDOW,)).fetchone()[0]
        personal_attempts = db.execute("""
            SELECT COUNT(*) FROM tracker_secondary_failures430
            WHERE username=? AND occurred_at>=?
        """, (username.casefold(), now - WINDOW)).fetchone()[0]

        if attempts >= 40 or personal_attempts >= 8:
            db.commit()
            return None

        row = db.execute("""
            SELECT id, salt, password_hash FROM users
            WHERE id>1 AND enabled=0 AND lower(username)=lower(?)
        """, (username,)).fetchone()

        salt = row[1] if row else b"\0" * 16
        candidate = auth.password_digest(password, salt)
        valid = bool(row) and hmac.compare_digest(candidate, row[2])

        if not valid:
            db.execute("""
                INSERT INTO tracker_secondary_failures430
                    (username, occurred_at) VALUES (?,?)
            """, (username.casefold(), now))
        else:
            db.execute(
                "DELETE FROM tracker_secondary_failures430 WHERE username=?",
                (username.casefold(),),
            )
        db.commit()

    if not valid:
        return None

    try:
        account = inspect_staged_account427(row[0])
    except (RuntimeError, PermissionError, ValueError, OSError, sqlite3.Error):
        return None

    return row[0] if account["username"].casefold() == username.casefold() else None


def _new_session(uid):
    raw = secrets.token_urlsafe(48)
    digest = hashlib.sha256(raw.encode()).hexdigest()
    now = int(time.time())

    with closing(auth.connect()) as db:
        _tables(db)
        db.execute("BEGIN IMMEDIATE")
        db.execute(
            "DELETE FROM tracker_secondary_sessions430 WHERE expires_at<=?",
            (now,),
        )
        db.execute("""
            INSERT INTO tracker_secondary_sessions430
                (token_hash, user_id, expires_at) VALUES (?,?,?)
        """, (digest, uid, now + LIFETIME))
        db.commit()
    return raw


def _session_user(token):
    if not isinstance(token, str) or not 40 <= len(token) <= 160:
        return None

    digest = hashlib.sha256(token.encode()).hexdigest()
    try:
        with closing(auth.connect()) as db:
            row = db.execute("""
                SELECT u.id FROM tracker_secondary_sessions430 s
                JOIN users u ON u.id=s.user_id
                WHERE s.token_hash=? AND s.expires_at>?
                  AND u.id>1 AND u.enabled=0
            """, (digest, int(time.time()))).fetchone()

        if row is None:
            return None

        inspect_staged_account427(row[0])
        return row[0]
    except (sqlite3.Error, OSError, ValueError, PermissionError, RuntimeError):
        return None


def _revoke(token):
    if not isinstance(token, str) or not 40 <= len(token) <= 160:
        return

    digest = hashlib.sha256(token.encode()).hexdigest()
    with closing(auth.connect()) as db:
        db.execute(
            "DELETE FROM tracker_secondary_sessions430 WHERE token_hash=?",
            (digest,),
        )
        db.commit()


def _csrf_response(response, token):
    response.set_cookie(
        CSRF_COOKIE, token,
        httponly=True, secure=True, samesite="strict",
        path="/secondary", max_age=900,
    )
    return response


def _csrf_check(request, form):
    if request.headers.get("sec-fetch-site", "").strip().lower() == "cross-site":
        raise HTTPException(403, "Cross-site request rejected")

    if not verify_pair(
        request.cookies.get(CSRF_COOKIE),
        str(form.get("csrf_token", "")),
        load_key(),
    ):
        raise HTTPException(403, "Invalid request token")


def _login_html(token, error=False):
    token = escape(token, quote=True)
    warning = (
        '<p role="alert">Sign-in unsuccessful.</p>'
        if error else ""
    )
    return f'''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="referrer" content="no-referrer">
<title>Secondary Preview</title>
<style>
body{{font:16px system-ui;max-width:430px;margin:5vh auto;padding:20px}}
input,button{{display:block;width:100%;padding:12px;margin:10px 0;font:inherit}}
</style>
</head>
<body>
<main>
<h1>Private Workspace Preview</h1>
<p>DEV only · Private workspace pilot</p>
{warning}
<form method="post" action="/secondary/login">
<input type="hidden" name="csrf_token" value="{token}">
<label>Username
<input name="username" autocomplete="username" required>
</label>
<label>Password
<input name="password" type="password" autocomplete="current-password" required>
</label>
<button type="submit">Sign In</button>
</form>
</main>
</body>
</html>'''


@preview_app.get("/")
def preview_root():
    require_preview()
    return RedirectResponse("/secondary/overview", status_code=303)


@preview_app.get("/login")
def login_get():
    require_preview()
    token = issue_token(load_key())
    response = HTMLResponse(
        _login_html(token),
        headers={"Cache-Control": "no-store"},
    )
    return _csrf_response(response, token)


@preview_app.post("/login")
async def login_post(request: Request):
    require_preview()
    form = await request.form()
    _csrf_check(request, form)
    username = str(form.get("username", ""))[:81].strip()
    password = str(form.get("password", ""))
    uid = _verify_credentials(username, password)

    if uid is None:
        token = issue_token(load_key())
        response = HTMLResponse(
            _login_html(token, error=True),
            status_code=401,
            headers={"Cache-Control": "no-store"},
        )
        return _csrf_response(response, token)

    raw = _new_session(uid)
    response = RedirectResponse(
        "/secondary/overview",
        status_code=303,
        headers={"Cache-Control": "no-store"},
    )
    response.set_cookie(
        COOKIE, raw,
        httponly=True, secure=True, samesite="strict",
        path="/secondary", max_age=LIFETIME,
    )
    return response


@preview_app.get("/overview")
def overview_get(request: Request):
    require_preview()

    if request.query_params:
        raise HTTPException(400, "Unsupported query parameters")

    uid = _session_user(request.cookies.get(COOKIE))
    if uid is None:
        return RedirectResponse("/secondary/login", status_code=303)

    try:
        report = read_workspace_overview429(uid)
    except (RuntimeError, PermissionError, ValueError, OSError):
        raise HTTPException(503, "Private workspace unavailable") from None

    if report.get("user_id") != uid:
        raise HTTPException(503, "Workspace identity mismatch")

    rows = "".join(
        "<tr><th>" + escape(key.replace("_", " ").title()) +
        "</th><td>" + str(value) + "</td></tr>"
        for key, value in report["counts"].items()
    )
    token = issue_token(load_key())
    html = f'''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="referrer" content="no-referrer">
<title>Private Workspace Overview</title>
</head>
<body>
<main>
<h1>Private Workspace Overview</h1>
<p>DEV-only private workspace pilot. Account {uid}.</p>
<p><a href="/secondary/vitals">Recent Vitals</a> ·
<a href="/secondary/doses">Recent Doses</a> ·
<a href="/secondary/inventory">My Inventory</a> ·
<a href="/secondary/readiness">Workspace Readiness</a> ·
<a href="/secondary/security">Session Security</a></p>
<table>{rows}</table>
<form method="post" action="/secondary/logout">
<input type="hidden" name="csrf_token" value="{escape(token, quote=True)}">
<button type="submit">Sign Out</button>
</form>
</main>
</body>
</html>'''
    response = HTMLResponse(
        html,
        headers={"Cache-Control": "no-store"},
    )
    return _csrf_response(response, token)


@preview_app.post("/logout")
async def logout_post(request: Request):
    require_preview()
    form = await request.form()
    _csrf_check(request, form)
    _revoke(request.cookies.get(COOKIE))

    response = RedirectResponse(
        "/secondary/login", status_code=303,
        headers={"Cache-Control": "no-store"},
    )
    response.delete_cookie(
        COOKIE,
        path="/secondary", secure=True,
        httponly=True, samesite="strict",
    )
    return response


# Release 432: read-only recent records, isolated per secondary workspace.
# No user-selected workspace, generic SQL, or write routes are provided.
from .worker_recent432 import read_recent432


def _html_value432(value):
    return escape("—" if value is None else str(value), quote=True)


def _recent_page432(request, kind):
    require_preview()
    if request.query_params:
        raise HTTPException(400, "Unsupported query parameters")

    uid = _session_user(request.cookies.get(COOKIE))
    if uid is None:
        return RedirectResponse("/secondary/login", status_code=303)

    try:
        report = read_recent432(uid, kind)
    except (RuntimeError, PermissionError, ValueError, OSError):
        raise HTTPException(503, "Private records unavailable") from None

    if report.get("user_id") != uid or report.get("kind") != kind:
        raise HTTPException(503, "Workspace identity mismatch")

    if kind == "vitals":
        title = "Recent Vitals"
        headers = ("Recorded", "Weight", "Blood Pressure", "Pulse", "Context")
        rows = []
        for item in report["items"]:
            weight = item["weight_kg"]
            if weight is not None:
                if config.WEIGHT_UNIT == "lb":
                    weight = f"{float(weight) * 2.20462262:.1f} lb"
                else:
                    weight = f"{float(weight):.1f} kg"
            bp = "—" if item["systolic"] is None else (
                str(item["systolic"])
                + ("/" + str(item["diastolic"]) if item["diastolic"] is not None else "")
            )
            rows.append((
                item["at"], weight, bp, item["pulse_bpm"], item["context"],
            ))
    else:
        title = "Recent Doses"
        headers = ("Recorded", "Compound", "Amount", "Type", "Site")
        rows = []
        for item in report["items"]:
            amount = str(item["amount"]) + " " + str(item["unit"])
            rows.append((
                item["at"], item["compound"], amount, item["kind"], item["site"],
            ))

    write_link = ""
    if kind == "vitals" and vital_writes_enabled433():
        write_link = '<p><a href="/secondary/vitals/new">Log Vitals</a></p>'
    if kind == "doses" and dose_writes_enabled434():
        write_link = '<p><a href="/secondary/doses/new">Log Dose</a></p>'

    columns = "".join("<th>" + escape(label) + "</th>" for label in headers)
    entries = "".join(
        "<tr>" + "".join("<td>" + _html_value432(cell) + "</td>" for cell in row)
        + "</tr>"
        for row in rows
    )
    if not rows:
        entries = '<tr><td colspan="5">No records yet.</td></tr>'

    html = f'''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="referrer" content="no-referrer">
<title>{escape(title)} · Tracker DEV</title>
<style>
body{{font:16px system-ui,sans-serif;max-width:850px;margin:0 auto;padding:16px}}
nav{{display:flex;gap:14px;flex-wrap:wrap}}
table{{border-collapse:collapse;width:100%;font-size:.9rem}}
th,td{{border-bottom:1px solid #aaa5;text-align:left;padding:9px 6px}}
.scroll{{overflow-x:auto}}
</style>
</head>
<body>
<main>
<h1>{escape(title)}</h1>
<p>Private workspace · Read-only</p>
<nav><a href="/secondary/overview">Overview</a>
<a href="/secondary/vitals">Vitals</a>
<a href="/secondary/doses">Doses</a>
<a href="/secondary/inventory">Inventory</a></nav>
{write_link}
<div class="scroll"><table><thead><tr>{columns}</tr></thead>
<tbody>{entries}</tbody></table></div>
<p>Showing up to 10 most recent records.</p>
</main>
</body>
</html>'''
    return HTMLResponse(html, headers={"Cache-Control": "no-store"})


@preview_app.get("/vitals")
def recent_vitals432(request: Request):
    return _recent_page432(request, "vitals")


@preview_app.get("/doses")
def recent_doses432(request: Request):
    return _recent_page432(request, "doses")


# Release 433: Explicitly opt-in, restricted secondary vitals logging.
# Dose and inventory writes remain DISABLED.
from datetime import datetime
from uuid import uuid4
from .worker_vital_write433 import form_payload433, create_vital_for_user433


def vital_writes_enabled433():
    return (
        preview_enabled()
        and os.getenv("TRACKER_SECONDARY_VITAL_WRITES433", "0") == "1"
    )


@preview_app.get("/vitals/new")
def vital_form433(request: Request):
    require_preview()
    if not vital_writes_enabled433():
        raise HTTPException(404, "Secondary vital logging unavailable")
    if request.query_params:
        raise HTTPException(400, "Unsupported query parameters")

    uid = _session_user(request.cookies.get(COOKIE))
    if uid is None:
        return RedirectResponse("/secondary/login", status_code=303)

    csrf = issue_token(load_key())
    nonce = str(uuid4())
    timestamp = datetime.now().strftime("%Y-%m-%dT%H:%M")
    unit = config.WEIGHT_UNIT
    alternate = "kg" if unit == "lb" else "lb"

    html = f'''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="referrer" content="no-referrer">
<title>Log Vitals · Tracker DEV</title>
<style>
*{{box-sizing:border-box}}
body{{font:16px system-ui,sans-serif;max-width:540px;margin:0 auto;padding:16px}}
label{{display:block;margin:14px 0}}
input,select,textarea,button{{font:inherit;width:100%;min-height:46px;padding:10px}}
fieldset{{border:1px solid #9995;border-radius:10px;margin:12px 0}}
.grid{{display:grid;grid-template-columns:1fr 1fr;gap:12px}}
button{{font-weight:700}}
</style>
</head>
<body>
<main>
<h1>Log Vitals</h1>
<p>Private workspace {uid} · DEV pilot</p>
<p><a href="/secondary/vitals">Recent Vitals</a></p>
<form method="post" action="/secondary/vitals/new" autocomplete="off">
<input type="hidden" name="csrf_token" value="{escape(csrf, quote=True)}">
<input type="hidden" name="submission_token" value="{nonce}">
<label>Measured at
<input type="datetime-local" name="measured_at"
value="{timestamp}" required></label>
<fieldset>
<legend>Weight</legend>
<div class="grid">
<label>Amount<input type="number" name="weight" min="0" step="0.01"
placeholder="Optional"></label>
<label>Unit<select name="weight_unit">
<option value="{unit}" selected>{unit}</option>
<option value="{alternate}">{alternate}</option>
</select></label>
</div>
</fieldset>
<fieldset>
<legend>Blood Pressure</legend>
<div class="grid">
<label>Systolic<input type="number" name="systolic" min="50" max="300"
inputmode="numeric" placeholder="Top"></label>
<label>Diastolic<input type="number" name="diastolic" min="20" max="200"
inputmode="numeric" placeholder="Bottom"></label>
</div>
</fieldset>
<label>Pulse (bpm)
<input type="number" name="pulse_bpm" min="20" max="300"
inputmode="numeric" placeholder="Optional"></label>
<label>Context
<input type="text" name="context" maxlength="80"
placeholder="Morning, seated"></label>
<label>Notes
<textarea name="notes" maxlength="2000" rows="3"></textarea></label>
<p>Enter at least one of weight, blood pressure, or pulse.</p>
<button type="submit">Save Vital Reading</button>
</form>
</main>
</body>
</html>'''
    return _csrf_response(
        HTMLResponse(html, headers={"Cache-Control": "no-store"}),
        csrf,
    )


@preview_app.post("/vitals/new")
async def vital_submit433(request: Request):
    require_preview()
    if not vital_writes_enabled433():
        raise HTTPException(404, "Secondary vital logging unavailable")
    if request.query_params:
        raise HTTPException(400, "Unsupported query parameters")

    uid = _session_user(request.cookies.get(COOKIE))
    if uid is None:
        raise HTTPException(401, "Secondary sign-in required")

    form = await request.form()
    _csrf_check(request, form)

    try:
        payload = form_payload433(form)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from None

    try:
        result = create_vital_for_user433(uid, payload)
    except (RuntimeError, PermissionError, OSError):
        raise HTTPException(503, "Private vitals storage unavailable") from None

    if result["status"] == "duplicate":
        raise HTTPException(409, "This vital reading was already recorded")

    return RedirectResponse(
        "/secondary/vitals",
        status_code=303,
        headers={"Cache-Control": "no-store"},
    )


# Release 434: DEV-only single-vial dose logging behind a second opt-in gate.
# Inventory accounting, all database reads, and inserts occur in the child.
from .worker_dose_write434 import form_payload434, request_dose434


def dose_writes_enabled434():
    return (
        preview_enabled()
        and os.getenv("TRACKER_SECONDARY_DOSE_WRITES434", "0") == "1"
    )


@preview_app.get("/doses/new")
def dose_form434(request: Request):
    require_preview()
    if not dose_writes_enabled434():
        raise HTTPException(404, "Secondary dose logging unavailable")
    if request.query_params:
        raise HTTPException(400, "Unsupported query parameters")

    uid = _session_user(request.cookies.get(COOKIE))
    if uid is None:
        return RedirectResponse("/secondary/login", status_code=303)

    try:
        options = request_dose434(uid, "options")["items"]
    except (RuntimeError, ValueError, PermissionError, OSError):
        raise HTTPException(503, "Private vial inventory unavailable") from None

    option_html = "".join(
        '<option value="' + str(item["id"]) + '">'
        + escape(item["label"])
        + " · "
        + escape(f'{item["remaining_base"]:g} {item["base_unit"]} available')
        + "</option>"
        for item in options
    )
    if not options:
        option_html = '<option value="">No available vials</option>'

    from .routers.doses import INJECTION_SITES
    site_html = '<option value="">Not recorded</option>' + "".join(
        '<option value="' + escape(site, quote=True) + '">'
        + escape(site) + '</option>'
        for site in INJECTION_SITES
    )
    token = issue_token(load_key())
    nonce = str(uuid4())
    timestamp = datetime.now().strftime("%Y-%m-%dT%H:%M")
    disabled = " disabled" if not options else ""

    html = f'''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="referrer" content="no-referrer">
<title>Log Dose · Tracker DEV</title>
<style>
*{{box-sizing:border-box}}
body{{font:16px system-ui,sans-serif;max-width:550px;margin:0 auto;padding:16px}}
label{{display:block;margin:14px 0}}
input,select,textarea,button{{font:inherit;width:100%;min-height:46px;padding:10px}}
.grid{{display:grid;grid-template-columns:1fr 1fr;gap:12px}}
button{{font-weight:700}}
</style>
</head>
<body>
<main>
<h1>Log Dose</h1>
<p>Private workspace {uid} · DEV pilot</p>
<p><a href="/secondary/doses">Recent Doses</a></p>
<form method="post" action="/secondary/doses/new" autocomplete="off">
<input type="hidden" name="csrf_token" value="{escape(token, quote=True)}">
<input type="hidden" name="submission_token" value="{nonce}">
<label>Vial
<select name="vial_id" required>{option_html}</select></label>
<label>Administered at
<input type="datetime-local" name="taken_at" value="{timestamp}" required></label>
<div class="grid">
<label>Amount
<input type="number" name="amount" min="0" step="any"
inputmode="decimal" required></label>
<label>Unit
<select name="unit">
<option value="mg">mg</option>
<option value="mcg">mcg</option>
<option value="IU">IU</option>
<option value="mL">mL</option>
<option value="uL">uL</option>
<option value="g">g</option>
</select></label>
</div>
<label>Injection Site
<select name="site">{site_html}</select></label>
<label>Notes
<textarea name="notes" maxlength="2000" rows="3"></textarea></label>
<p>Only a single-vial dose is supported. Supply deductions,
waste entries, and corrections are not available in this pilot.</p>
<button type="submit"{disabled}>Record Dose</button>
</form>
</main>
</body>
</html>'''
    return _csrf_response(
        HTMLResponse(html, headers={"Cache-Control": "no-store"}),
        token,
    )


@preview_app.post("/doses/new")
async def dose_submit434(request: Request):
    require_preview()
    if not dose_writes_enabled434():
        raise HTTPException(404, "Secondary dose logging unavailable")
    if request.query_params:
        raise HTTPException(400, "Unsupported query parameters")

    uid = _session_user(request.cookies.get(COOKIE))
    if uid is None:
        raise HTTPException(401, "Secondary sign-in required")

    form = await request.form()
    _csrf_check(request, form)
    try:
        payload = form_payload434(form)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from None

    try:
        result = request_dose434(uid, "create_dose", payload)
    except (RuntimeError, PermissionError, OSError):
        raise HTTPException(503, "Private dose recording unavailable") from None

    if result["status"] == "duplicate":
        raise HTTPException(409, "This dose submission was already used")
    if result["status"] == "rejected":
        raise HTTPException(422, result["error"])

    return RedirectResponse(
        "/secondary/doses",
        status_code=303,
        headers={"Cache-Control": "no-store"},
    )


# Release 435: private inventory listing and strictly create-only mutations.
from .worker_inventory435 import (
    request_inventory435, form_compound435, form_vial435,
)
from .models import CATEGORIES
from .units import CONTENT_UNITS


def inventory_writes_enabled435():
    return (
        preview_enabled()
        and os.getenv("TRACKER_SECONDARY_INVENTORY_WRITES435", "0") == "1"
    )


@preview_app.get("/inventory")
def inventory_page435(request: Request):
    require_preview()
    if request.query_params:
        raise HTTPException(400, "Unsupported query parameters")

    uid = _session_user(request.cookies.get(COOKIE))
    if uid is None:
        return RedirectResponse("/secondary/login", status_code=303)

    try:
        report = request_inventory435(uid, "inventory")
    except (RuntimeError, OSError, PermissionError, ValueError):
        raise HTTPException(503, "Private inventory unavailable") from None

    compounds = report["compounds"]
    vials = report["vials"]
    writable = inventory_writes_enabled435()

    list_compounds = "".join(
        "<li><strong>" + escape(row["name"]) + "</strong>"
        + " · " + escape(row["category"])
        + " · " + escape(row["primary_unit"]) + "</li>"
        for row in compounds
    ) or "<li>No compounds yet.</li>"
    list_vials = "".join(
        "<li><strong>" + escape(row["compound"]) + "</strong>"
        + " · " + escape(row["label"] or f'Vial #{row["id"]}')
        + " · " + escape(f'{row["content_value"]:g} {row["content_unit"]}')
        + " · " + escape(row["status"]) + "</li>"
        for row in vials
    ) or "<li>No vials yet.</li>"

    forms = ""
    csrf = None
    if writable:
        csrf = issue_token(load_key())
        category_choices = "".join(
            '<option value="' + escape(value, quote=True) + '">'
            + escape(value.title()) + '</option>'
            for value in CATEGORIES
        )
        content_choices = "".join(
            '<option value="' + escape(value, quote=True) + '"'
            + (' selected' if value == 'mg' else '') + '>'
            + escape(value) + '</option>'
            for value in CONTENT_UNITS
        )
        compounds_choices = "".join(
            '<option value="' + str(item["id"]) + '">'
            + escape(item["name"]) + '</option>'
            for item in compounds
        )
        disabled = "" if compounds else " disabled"
        compound_token = str(uuid4())
        vial_token = str(uuid4())

        forms = f'''<section>
<h2>Add Compound</h2>
<form method="post" action="/secondary/inventory/compounds" autocomplete="off">
<input type="hidden" name="csrf_token" value="{escape(csrf, quote=True)}">
<input type="hidden" name="submission_token" value="{compound_token}">
<label>Name<input name="name" maxlength="120" required></label>
<div class="twocol">
<label>Category<select name="category">{category_choices}</select></label>
<label>Primary Unit<select name="primary_unit">{content_choices}</select></label>
</div>
<label>Notes<textarea name="notes" maxlength="2000" rows="2"></textarea></label>
<button type="submit">Add Compound</button>
</form>
</section>
<section>
<h2>Add Single Vial</h2>
<form method="post" action="/secondary/inventory/vials" autocomplete="off">
<input type="hidden" name="csrf_token" value="{escape(csrf, quote=True)}">
<input type="hidden" name="submission_token" value="{vial_token}">
<label>Compound<select name="compound_id" required>
{compounds_choices}</select></label>
<label>Label<input name="label" maxlength="160"
placeholder="Optional vial name"></label>
<div class="twocol">
<label>Content<input name="content_value" type="number"
min="0.000001" step="any" inputmode="decimal" required></label>
<label>Unit<select name="content_unit">{content_choices}</select></label>
</div>
<div class="twocol">
<label>Form<select name="form">
<option value="lyophilized">Lyophilized</option>
<option value="solution">Solution</option>
</select></label>
<label>Liquid Volume (mL)<input name="volume_ml" type="number"
min="0.0001" step="any" inputmode="decimal"
placeholder="Required for solutions"></label>
</div>
<div class="twocol">
<label>Lot<input name="lot" maxlength="80"></label>
<label>Cap Color<input name="cap_color" maxlength="60"></label>
</div>
<label>Notes<textarea name="notes" maxlength="2000" rows="2"></textarea></label>
<p>Creates one sealed vial without a purchase record.
Bulk kits, reconstitution, editing, and deletion are not available here.</p>
<button type="submit"{disabled}>Add Vial</button>
</form>
</section>'''

    reconstitution_link = (
        '<p><a href="/secondary/reconstitution">Record Reconstitution</a></p>'
        if reconstitution_enabled436() else ""
    )

    html = f'''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="referrer" content="no-referrer">
<title>Private Inventory · Tracker DEV</title>
<style>
*{{box-sizing:border-box}}
body{{font:16px system-ui,sans-serif;max-width:650px;margin:0 auto;padding:16px}}
nav{{display:flex;flex-wrap:wrap;gap:14px;margin-bottom:18px}}
section{{border:1px solid #9995;border-radius:12px;padding:14px;margin:16px 0}}
label{{display:block;margin:12px 0}}
input,select,textarea,button{{font:inherit;min-height:46px;padding:10px;width:100%}}
.twocol{{display:grid;grid-template-columns:1fr 1fr;gap:12px}}
@media(max-width:390px){{.twocol{{grid-template-columns:1fr}}}}
li{{margin-bottom:8px;overflow-wrap:anywhere}}
button{{font-weight:700}}
</style>
</head>
<body><main>
<h1>My Inventory</h1>
<p>Private workspace {uid} · DEV preview</p>
<p><a href="/secondary/supplies">My Supplies</a> ·
<a href="/secondary/reconcile">Reconcile Vial Inventory</a></p>
{reconstitution_link}
<nav><a href="/secondary/overview">Overview</a>
<a href="/secondary/vitals">Vitals</a>
<a href="/secondary/doses">Doses</a></nav>
{forms}
<section><h2>Compounds</h2><ul>{list_compounds}</ul></section>
<section><h2>Vials</h2><ul>{list_vials}</ul></section>
</main></body></html>'''

    response = HTMLResponse(html, headers={"Cache-Control": "no-store"})
    return _csrf_response(response, csrf) if csrf is not None else response


async def _inventory_submit435(request, action):
    require_preview()
    if not inventory_writes_enabled435():
        raise HTTPException(404, "Secondary inventory creation unavailable")
    if request.query_params:
        raise HTTPException(400, "Unsupported query parameters")

    uid = _session_user(request.cookies.get(COOKIE))
    if uid is None:
        raise HTTPException(401, "Secondary sign-in required")

    form = await request.form()
    _csrf_check(request, form)
    try:
        if action == "create_compound":
            payload = form_compound435(form)
        else:
            payload = form_vial435(form)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from None

    try:
        result = request_inventory435(uid, action, payload)
    except (RuntimeError, PermissionError, OSError, ValueError):
        raise HTTPException(503, "Private inventory write unavailable") from None
    if result["status"] == "duplicate":
        raise HTTPException(409, "This inventory submission was already used")
    if result["status"] == "rejected":
        raise HTTPException(422, result["error"])
    return RedirectResponse(
        "/secondary/inventory", status_code=303,
        headers={"Cache-Control": "no-store"},
    )


@preview_app.post("/inventory/compounds")
async def create_private_compound435(request: Request):
    return await _inventory_submit435(request, "create_compound")


@preview_app.post("/inventory/vials")
async def create_private_vial435(request: Request):
    return await _inventory_submit435(request, "create_vial")


# Release 436: single-use private reconstitution recording with no supply debit.
from .worker_reconstitution436 import (
    request_reconstitution436, form_payload436,
)


def reconstitution_enabled436():
    return (
        preview_enabled()
        and os.getenv("TRACKER_SECONDARY_RECONSTITUTION_WRITES436", "0") == "1"
    )


@preview_app.get("/reconstitution")
def private_reconstitution_form436(request: Request):
    require_preview()
    if not reconstitution_enabled436():
        raise HTTPException(404, "Secondary reconstitution unavailable")
    if request.query_params:
        raise HTTPException(400, "Unsupported query parameters")

    uid = _session_user(request.cookies.get(COOKIE))
    if uid is None:
        return RedirectResponse("/secondary/login", status_code=303)

    try:
        options = request_reconstitution436(uid, "options")["options"]
    except (RuntimeError, PermissionError, ValueError, OSError):
        raise HTTPException(503, "Private vial inventory unavailable") from None

    choices = "".join(
        '<option value="' + str(item["id"]) + '">'
        + escape(item["label"])
        + " · "
        + escape(f'{item["content_value"]:g} {item["content_unit"]}')
        + "</option>"
        for item in options
    )
    if not options:
        choices = '<option value="">No eligible dry vials</option>'

    disabled = " disabled" if not options else ""
    csrf = issue_token(load_key())
    nonce = str(uuid4())
    html = f'''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="referrer" content="no-referrer">
<title>Reconstitution · Tracker DEV</title>
<style>
*{{box-sizing:border-box}}
body{{font:16px system-ui,sans-serif;max-width:540px;margin:0 auto;padding:16px}}
label{{display:block;margin:14px 0}}
input,select,button{{font:inherit;min-height:46px;padding:10px;width:100%}}
button{{font-weight:700}}
</style>
</head>
<body><main>
<h1>Record Reconstitution</h1>
<p>Private workspace {uid} · DEV-only pilot</p>
<p><a href="/secondary/inventory">My Inventory</a></p>
<form method="post" action="/secondary/reconstitution" autocomplete="off">
<input type="hidden" name="csrf_token" value="{escape(csrf, quote=True)}">
<input type="hidden" name="submission_token" value="{nonce}">
<label>Dry Vial
<select name="vial_id" required>{choices}</select></label>
<label>Liquid volume added (mL)
<input name="volume_ml" type="number" min="0.0001" max="1000"
step="any" inputmode="decimal" placeholder="Actual measured amount"
required></label>
<p>Enter the volume you actually added; this form does not recommend
a volume or dose. This records the vial volume and preparation event.
It does not deduct BAC water or disposable supplies.</p>
<p>Existing reconstitutions, dosed vials, corrections, and
repeat preparations are not supported in this pilot.</p>
<button type="submit"{disabled}>Record Reconstitution</button>
</form>
</main></body></html>'''
    return _csrf_response(
        HTMLResponse(html, headers={"Cache-Control": "no-store"}),
        csrf,
    )


@preview_app.post("/reconstitution")
async def private_reconstitution_submit436(request: Request):
    require_preview()
    if not reconstitution_enabled436():
        raise HTTPException(404, "Secondary reconstitution unavailable")
    if request.query_params:
        raise HTTPException(400, "Unsupported query parameters")

    uid = _session_user(request.cookies.get(COOKIE))
    if uid is None:
        raise HTTPException(401, "Secondary sign-in required")
    form = await request.form()
    _csrf_check(request, form)
    try:
        payload = form_payload436(form)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from None

    try:
        result = request_reconstitution436(uid, "reconstitute", payload)
    except (RuntimeError, PermissionError, OSError, ValueError):
        raise HTTPException(
            503, "Private reconstitution storage unavailable"
        ) from None

    if result["status"] == "duplicate":
        raise HTTPException(409, "This submission identifier was already used")
    if result["status"] == "rejected":
        raise HTTPException(422, result["error"])
    return RedirectResponse(
        "/secondary/inventory",
        status_code=303,
        headers={"Cache-Control": "no-store"},
    )


# Release 437: read-only vial reconciliation and gated audited corrections.
from .worker_reconciliation437 import (
    request_reconciliation437, form_correction437,
)


def corrections_enabled437():
    return (
        preview_enabled()
        and os.getenv("TRACKER_SECONDARY_VIAL_CORRECTIONS437", "0") == "1"
    )


def _reconciliation_number437(value, unit):
    return escape(f"{float(value):g} {unit}")


@preview_app.get("/reconcile")
def reconcile_page437(request: Request):
    require_preview()
    if request.query_params:
        raise HTTPException(400, "Unsupported query parameters")

    uid = _session_user(request.cookies.get(COOKIE))
    if uid is None:
        return RedirectResponse("/secondary/login", status_code=303)
    try:
        report = request_reconciliation437(uid, "report")
    except (RuntimeError, PermissionError, ValueError, OSError):
        raise HTTPException(503, "Private reconciliation unavailable") from None

    results = []
    for item in report["items"]:
        ref = f'/secondary/reconcile/vials/{item["id"]}'
        header = escape(item["compound"]) + " · " + escape(
            item["label"] or f'Vial #{item["id"]}'
        )
        warning = "".join(
            "<li>" + escape(value) + "</li>"
            for value in item["warnings"]
        )
        results.append(
            '<section><h2><a href="' + ref + '">' + header + '</a></h2>'
            + "<p>Status: " + escape(item["status"])
            + " · On-hand: " + _reconciliation_number437(
                item["remaining"], item["unit"],
            )
            + " · Consumed: " + _reconciliation_number437(
                item["used"], item["unit"],
            )
            + " · Original: " + _reconciliation_number437(
                item["total"], item["unit"],
            ) + "</p>"
            + ("<ul>" + warning + "</ul>" if warning else "")
            + "</section>"
        )
    listing = "".join(results) or "<p>No vials recorded.</p>"

    html = f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="referrer" content="no-referrer">
<title>Inventory Reconciliation · Tracker DEV</title>
<style>
body{{font:16px system-ui,sans-serif;max-width:700px;margin:auto;padding:16px}}
section{{border:1px solid #9995;border-radius:10px;padding:12px;margin:12px 0}}
h2{{font-size:1.1rem;margin:0}}
p{{line-height:1.5}}
</style></head><body><main>
<h1>Vial Inventory Reconciliation</h1>
<p>Private workspace {uid} · Read-only stock accounting</p>
<p><a href="/secondary/inventory">My Inventory</a></p>
<p>Tracked quantity reflects vial contents minus recorded administrations,
waste, and blend transfers. It does not verify physical stock.</p>
{listing}
<p>Showing up to 100 most recent vials.</p>
</main></body></html>'''
    return HTMLResponse(html, headers={"Cache-Control": "no-store"})


@preview_app.get("/reconcile/vials/{vial_id}")
def reconcile_vial_detail437(vial_id: int, request: Request):
    require_preview()
    if request.query_params:
        raise HTTPException(400, "Unsupported query parameters")
    if not 1 <= vial_id <= 2147483647:
        raise HTTPException(404, "Vial not found")

    uid = _session_user(request.cookies.get(COOKIE))
    if uid is None:
        return RedirectResponse("/secondary/login", status_code=303)
    try:
        report = request_reconciliation437(uid, "detail", vial_id=vial_id)
    except (RuntimeError, PermissionError, ValueError, OSError):
        raise HTTPException(503, "Private vial detail unavailable") from None
    if report["status"] == "missing":
        raise HTTPException(404, "Vial not found")

    item = report["item"]
    audits = report["audit"]
    warnings = "".join(
        "<li>" + escape(warning) + "</li>"
        for warning in item["warnings"]
    ) or "<li>No reconciliation warnings.</li>"
    audit_html = ""
    for event in audits:
        changes = []
        for field in ("label", "lot", "cap_color", "status"):
            prior = event["before"].get(field, "")
            later = event["after"].get(field, "")
            if prior != later:
                changes.append(
                    "<li>" + escape(field.replace("_", " ").title())
                    + ": " + escape(str(prior)) + " → "
                    + escape(str(later)) + "</li>"
                )
        audit_html += (
            '<section><strong>' + escape(event["at"])
            + " · " + escape(event["action"])
            + '</strong><p>' + escape(event["reason"])
            + '</p><ul>' + "".join(changes) + "</ul></section>"
        )
    audit_html = audit_html or "<p>No vial correction history recorded.</p>"

    edit = ""
    token = None
    if corrections_enabled437():
        token = issue_token(load_key())
        nonce = str(uuid4())
        if item["status"] == "sealed":
            statuses = ("sealed", "discarded")
        elif item["status"] == "in_use":
            statuses = ("in_use", "finished", "discarded")
        else:
            statuses = (item["status"],)
        choices = "".join(
            '<option value="' + state + '"'
            + (" selected" if state == item["status"] else "")
            + ">" + state.replace("_", " ").title() + "</option>"
            for state in statuses
        )
        edit = f'''<section><h2>Audited Vial Correction</h2>
<p>Only metadata and one-way lifecycle closures can change here.
Contents, concentration, and dose history cannot be edited.</p>
<form method="post" action="/secondary/reconcile/correct">
<input type="hidden" name="csrf_token" value="{escape(token, quote=True)}">
<input type="hidden" name="submission_token" value="{nonce}">
<input type="hidden" name="vial_id" value="{item["id"]}">
<input type="hidden" name="snapshot" value="{item["snapshot"]}">
<label>Label<input name="label" maxlength="160"
value="{escape(item["label"], quote=True)}"></label>
<label>Lot<input name="lot" maxlength="80"
value="{escape(item["lot"], quote=True)}"></label>
<label>Cap Color<input name="cap_color" maxlength="60"
value="{escape(item["cap_color"], quote=True)}"></label>
<label>Status<select name="status">{choices}</select></label>
<label>Reason for correction (required, 8–400 characters)
<textarea name="reason" minlength="8" maxlength="400"
rows="3" required></textarea></label>
<button type="submit">Save Audited Correction</button>
</form></section>'''

    html = f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="referrer" content="no-referrer">
<title>Vial Reconciliation · Tracker DEV</title>
<style>
*{{box-sizing:border-box}}
body{{font:16px system-ui,sans-serif;max-width:630px;margin:auto;padding:16px}}
section{{border:1px solid #9995;border-radius:12px;padding:14px;margin:14px 0}}
label{{display:block;margin:12px 0}}
input,select,textarea,button{{font:inherit;width:100%;min-height:46px;padding:10px}}
button{{font-weight:700}}li{{overflow-wrap:anywhere}}
</style></head><body><main>
<h1>{escape(item["compound"])} · {escape(item["label"] or f'Vial #{vial_id}')}</h1>
<p><a href="/secondary/reconcile">Back to Reconciliation</a></p>
<p>Current status: <strong>{escape(item["status"])}</strong></p>
<p>Original: {_reconciliation_number437(item["total"], item["unit"])}</p>
<p>Recorded use: {_reconciliation_number437(item["used"], item["unit"])}</p>
<p>Remaining: {_reconciliation_number437(item["remaining"], item["unit"])}</p>
<p>Doses: {item["dose_count"]} · Reconstitutions: {item["reconstitution_count"]}</p>
<section><h2>Reconciliation Warnings</h2><ul>{warnings}</ul></section>
{edit}
<section><h2>Recent Audit History</h2>{audit_html}</section>
</main></body></html>'''
    response = HTMLResponse(html, headers={"Cache-Control": "no-store"})
    return _csrf_response(response, token) if token is not None else response


@preview_app.post("/reconcile/correct")
async def reconcile_vial_post437(request: Request):
    require_preview()
    if not corrections_enabled437():
        raise HTTPException(404, "Vial corrections unavailable")
    if request.query_params:
        raise HTTPException(400, "Unsupported query parameters")

    uid = _session_user(request.cookies.get(COOKIE))
    if uid is None:
        raise HTTPException(401, "Secondary sign-in required")

    form = await request.form()
    _csrf_check(request, form)
    try:
        payload = form_correction437(form)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from None

    try:
        report = request_reconciliation437(uid, "correct", payload=payload)
    except (RuntimeError, OSError, PermissionError, ValueError):
        raise HTTPException(503, "Private vial correction unavailable") from None

    if report["status"] == "duplicate":
        raise HTTPException(409, "This correction submission was already used")
    if report["status"] == "stale":
        raise HTTPException(409, "Vial changed; refresh before correcting it")
    if report["status"] == "rejected":
        raise HTTPException(422, report["error"])

    return RedirectResponse(
        f'/secondary/reconcile/vials/{payload["vial_id"]}',
        status_code=303,
        headers={"Cache-Control": "no-store"},
    )


# Release 438: private read-only supply inventory and gated supply intake.
from .worker_supply438 import request_supply438, form_create438, KINDS


def supply_writes_enabled438():
    return (
        preview_enabled()
        and os.getenv("TRACKER_SECONDARY_SUPPLY_WRITES438", "0") == "1"
    )


@preview_app.get("/supplies")
def secondary_supplies438(request: Request):
    require_preview()
    if request.query_params:
        raise HTTPException(400, "Unsupported query parameters")
    uid = _session_user(request.cookies.get(COOKIE))
    if uid is None:
        return RedirectResponse("/secondary/login", status_code=303)
    try:
        report = request_supply438(uid, "list")
    except (RuntimeError, PermissionError, ValueError, OSError):
        raise HTTPException(503, "Private supply inventory unavailable") from None

    rows = "".join(
        '<li><strong>' + escape(item["name"]) + '</strong> · '
        + escape(item["kind"].replace("_", " ").title())
        + ' · On hand ' + escape(
            f'{item["remaining"]:g} {item["unit"]}'
        ) + ' / ' + escape(
            f'{item["quantity"]:g} {item["unit"]}'
        ) + '</li>'
        for item in report["supplies"]
    ) or "<li>No supplies recorded yet.</li>"
    writable = supply_writes_enabled438()
    csrf = issue_token(load_key()) if writable else None
    form = ""
    if writable:
        kind_options = "".join(
            '<option value="' + escape(kind, quote=True) + '">'
            + escape(kind.replace("_", " ").title()) + '</option>'
            for kind in KINDS
        )
        form = f'''<section><h2>Add Supply Inventory</h2>
<form method="post" action="/secondary/supplies" autocomplete="off">
<input type="hidden" name="csrf_token" value="{escape(csrf, quote=True)}">
<input type="hidden" name="submission_token" value="{uuid4()}">
<label>Supply Name<input name="name" maxlength="160" required></label>
<label>Type<select name="kind">{kind_options}</select></label>
<label>Purchased / Added Quantity
<input name="quantity" type="number" min="0.0001" step="any"
inputmode="decimal" required></label>
<p>BAC water uses mL. Disposables use whole item counts.</p>
<label>Notes<textarea name="notes" maxlength="2000" rows="3"></textarea></label>
<button type="submit">Add Supply</button>
</form></section>'''
    usage_link439 = (
        '<p><a href="/secondary/supplies/use">Log Supply Use</a></p>'
        if supply_use_enabled439() else ""
    )
    html = f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="referrer" content="no-referrer">
<title>My Supplies · Tracker DEV</title>
<style>
*{{box-sizing:border-box}}
body{{font:16px system-ui,sans-serif;max-width:570px;margin:auto;padding:16px}}
section{{border:1px solid #9995;border-radius:12px;padding:14px;margin:14px 0}}
label{{display:block;margin:14px 0}}
input,select,textarea,button{{font:inherit;min-height:46px;padding:10px;width:100%}}
button{{font-weight:700}}
li{{margin:12px 0;overflow-wrap:anywhere}}
</style></head><body><main>
<h1>My Supplies</h1>
<p>Private workspace {uid} · DEV preview</p>
<p><a href="/secondary/inventory">My Inventory</a></p>
<p>Supply intake is separate from administration history.
Use the explicit consumption form to link a supply to a recorded event.</p>
{usage_link439}
{form}
<section><h2>Supply Inventory</h2><ul>{rows}</ul></section>
</main></body></html>'''
    response = HTMLResponse(html, headers={"Cache-Control": "no-store"})
    return _csrf_response(response, csrf) if csrf is not None else response


@preview_app.post("/supplies")
async def secondary_supply_create438(request: Request):
    require_preview()
    if not supply_writes_enabled438():
        raise HTTPException(404, "Private supply intake unavailable")
    if request.query_params:
        raise HTTPException(400, "Unsupported query parameters")
    uid = _session_user(request.cookies.get(COOKIE))
    if uid is None:
        raise HTTPException(401, "Secondary sign-in required")

    form = await request.form()
    _csrf_check(request, form)
    try:
        payload = form_create438(form)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from None
    try:
        result = request_supply438(uid, "create", payload)
    except (RuntimeError, PermissionError, ValueError, OSError):
        raise HTTPException(503, "Private supply intake unavailable") from None
    if result["status"] == "duplicate":
        raise HTTPException(409, "This supply submission was already used")
    return RedirectResponse(
        "/secondary/supplies", status_code=303,
        headers={"Cache-Control": "no-store"},
    )


# Release 439: explicit supply consumption linked to a recorded private event.
from .worker_supply_use439 import request_use439, form_use439


def supply_use_enabled439():
    return (
        preview_enabled()
        and os.getenv("TRACKER_SECONDARY_SUPPLY_USE439", "0") == "1"
    )


@preview_app.get("/supplies/use")
def secondary_supply_use_form439(request: Request):
    require_preview()
    if not supply_use_enabled439():
        raise HTTPException(404, "Supply-use logging unavailable")
    if request.query_params:
        raise HTTPException(400, "Unsupported query parameters")

    uid = _session_user(request.cookies.get(COOKIE))
    if uid is None:
        return RedirectResponse("/secondary/login", status_code=303)

    try:
        report = request_use439(uid, "options")
    except (RuntimeError, PermissionError, ValueError, OSError):
        raise HTTPException(503, "Private supply-use options unavailable") from None

    choices = "".join(
        '<option value="' + str(item["id"]) + '">'
        + escape(item["name"])
        + ' · ' + escape(item["kind"].replace("_", " ").title())
        + ' · ' + escape(f'{item["remaining"]:g} {item["unit"]} available')
        + '</option>'
        for item in report["supplies"]
    ) or '<option value="">No supplies available</option>'

    references = "".join(
        '<option value="' + escape(
            item["type"] + ":" + str(item["id"]), quote=True,
        ) + '">' + escape(item["label"]) + '</option>'
        for item in report["references"]
    ) or '<option value="">No dose or reconstitution history</option>'

    history = "".join(
        '<li>' + escape(item["supply"]) + " · "
        + escape(f'{item["amount"]:g} {item["unit"]}')
        + ' · ' + escape(item["reference"]) + '</li>'
        for item in report["history"]
    ) or "<li>No supply consumption recorded yet.</li>"

    disabled = (
        " disabled"
        if not report["supplies"] or not report["references"]
        else ""
    )
    csrf = issue_token(load_key())
    html = f'''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="referrer" content="no-referrer">
<title>Log Supply Use · Tracker DEV</title>
<style>
*{{box-sizing:border-box}}
body{{font:16px system-ui,sans-serif;max-width:570px;margin:auto;padding:16px}}
label{{display:block;margin:14px 0}}
input,select,textarea,button{{font:inherit;width:100%;min-height:46px;padding:10px}}
section{{border:1px solid #9995;border-radius:12px;padding:14px;margin:16px 0}}
button{{font-weight:700}}li{{margin:12px 0;overflow-wrap:anywhere}}
</style>
</head>
<body><main>
<h1>Log Supply Use</h1>
<p>Private workspace {uid} · DEV pilot</p>
<p><a href="/secondary/supplies">My Supplies</a></p>
<form action="/secondary/supplies/use" method="post" autocomplete="off">
<input type="hidden" name="csrf_token" value="{escape(csrf, quote=True)}">
<input type="hidden" name="submission_token" value="{uuid4()}">
<label>Supply<select name="supply_id" required>{choices}</select></label>
<label>Link to recorded event
<select name="reference" required>{references}</select></label>
<label>Actual quantity used
<input type="number" name="amount" min="0.0001" step="any"
inputmode="decimal" required></label>
<label>Notes or reason
<textarea name="notes" maxlength="400" rows="3"></textarea></label>
<p>BAC water uses mL and can only be linked to a reconstitution.
Its cumulative recorded use cannot exceed the volume added.
Needles, syringes, swabs and other disposables use whole counts.</p>
<p>Supply use is never inferred from a dose. Record only what was actually used.
The same supply cannot be linked twice to the same event in this pilot.</p>
<button type="submit"{disabled}>Record Supply Use</button>
</form>
<section><h2>Recent Supply Use</h2><ul>{history}</ul></section>
</main></body></html>'''
    return _csrf_response(
        HTMLResponse(html, headers={"Cache-Control": "no-store"}),
        csrf,
    )


@preview_app.post("/supplies/use")
async def secondary_supply_use_submit439(request: Request):
    require_preview()
    if not supply_use_enabled439():
        raise HTTPException(404, "Supply-use logging unavailable")
    if request.query_params:
        raise HTTPException(400, "Unsupported query parameters")

    uid = _session_user(request.cookies.get(COOKIE))
    if uid is None:
        raise HTTPException(401, "Secondary sign-in required")

    form = await request.form()
    _csrf_check(request, form)
    try:
        payload = form_use439(form)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from None

    try:
        result = request_use439(uid, "use", payload)
    except (RuntimeError, PermissionError, ValueError, OSError):
        raise HTTPException(503, "Private supply-use storage unavailable") from None

    if result["status"] == "duplicate":
        raise HTTPException(409, "This supply submission identifier was used")
    if result["status"] == "rejected":
        raise HTTPException(422, result["error"])
    return RedirectResponse(
        "/secondary/supplies/use", status_code=303,
        headers={"Cache-Control": "no-store"},
    )


# Release 440: private capability readiness, without enabling new features.
# TRACKER_SECONDARY_LOCKDOWN440=1 is a gateway-level emergency denial.
# It does not erase credentials or private data.
@preview_app.get("/readiness")
def secondary_readiness440(request: Request):
    require_preview()
    if request.query_params:
        raise HTTPException(400, "Unsupported query parameters")

    uid = _session_user(request.cookies.get(COOKIE))
    if uid is None:
        return RedirectResponse("/secondary/login", status_code=303)

    try:
        report = read_workspace_overview429(uid)
    except (RuntimeError, PermissionError, ValueError, OSError):
        raise HTTPException(
            503, "Private workspace readiness unavailable"
        ) from None
    if report.get("user_id") != uid:
        raise HTTPException(503, "Workspace identity mismatch")

    capabilities = (
        ("vitals", "Log Vitals", vital_writes_enabled433(),
         "/secondary/vitals/new"),
        ("doses", "Log Doses", dose_writes_enabled434(),
         "/secondary/doses/new"),
        ("inventory", "Create Compounds and Vials", inventory_writes_enabled435(),
         "/secondary/inventory"),
        ("reconstitution", "Record Reconstitution", reconstitution_enabled436(),
         "/secondary/reconstitution"),
        ("vial_corrections", "Correct Vial Metadata", corrections_enabled437(),
         "/secondary/reconcile"),
        ("supply_intake", "Add Supply Inventory", supply_writes_enabled438(),
         "/secondary/supplies"),
        ("supply_use", "Record Supply Use", supply_use_enabled439(),
         "/secondary/supplies/use"),
    )
    capabilities_html = "".join(
        '<tr data-feature="' + key + '"><th scope="row">'
        + escape(title) + "</th><td>"
        + ("Enabled (DEV)" if enabled else "Disabled")
        + "</td><td>"
        + (
            '<a href="' + escape(destination, quote=True)
            + '">Open</a>'
            if enabled else "—"
        )
        + "</td></tr>"
        for key, title, enabled, destination in capabilities
    )

    counts = report["counts"]
    counts_html = "".join(
        "<tr><th scope=\"row\">"
        + escape(key.replace("_", " ").title())
        + "</th><td>" + str(int(value)) + "</td></tr>"
        for key, value in counts.items()
    )
    html = f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="referrer" content="no-referrer">
<title>Workspace Readiness · Tracker DEV</title>
<style>
*{{box-sizing:border-box}}
body{{font:16px system-ui,sans-serif;max-width:650px;margin:auto;padding:16px}}
table{{border-collapse:collapse;width:100%;font-size:.92rem}}
th,td{{border-bottom:1px solid #9995;padding:10px 6px;text-align:left}}
.scroll{{overflow-x:auto}} p{{line-height:1.5}}
</style></head><body><main>
<h1>Workspace Readiness</h1>
<p>DEV-only secondary workspace {uid} · Isolated data and login preview</p>
<p><a href="/secondary/overview">Overview</a> ·
<a href="/secondary/inventory">Inventory</a> ·
<a href="/secondary/security">Session Security</a></p>
<p>These controls do not activate normal Tracker multi-user login.
Only the enabled pilot operations below permit writes.</p>
<h2>Workspace Records</h2>
<div class="scroll"><table>{counts_html}</table></div>
<h2>Write Permissions</h2>
<div class="scroll"><table>
<thead><tr><th>Operation</th><th>Status</th><th>Page</th></tr></thead>
<tbody>{capabilities_html}</tbody>
</table></div>
<p>Operators can suspend all secondary gateway access by setting
<code>TRACKER_SECONDARY_LOCKDOWN440=1</code> in the DEV service environment.
Production remains unavailable.</p>
<section><h2>Recovery Coverage</h2>
<p>Recovery warning: the existing standard Tracker backup archives the
administrator database and uploads, but does not include staged secondary
user databases or <code>tracker-auth.sqlite3</code>. Automatic secondary
backup and restore coverage is not yet available; do not use the standard
backup as evidence of recovery for secondary accounts.</p>
<p>A separate DEV-only root-operated recovery command is available:
<code>python scripts/tracker-secondary-backup442.py create</code>.
It captures individually consistent SQLite snapshots and private uploads,
then verifies an isolated restore without touching live records. It does not provide an atomic snapshot across users,
off-host encryption, or a live restore function. An optional nightly
systemd timer can be installed separately after Release 443;
it is never enabled by deployment. Root operators can use
<code>python scripts/tracker-secondary-ops443.py status</code>
to independently verify the newest archive and detect stale backups.
Recovery readiness requires an actual verified archive.</p></section>
</main></body></html>'''
    return HTMLResponse(
        html, headers={"Cache-Control": "no-store"}
    )


# Release 441: self-service secondary session review and scoped revocation.
# No user ID or arbitrary session hash is accepted from the browser.
from .secondary_sessions441 import session_overview441, revoke_other_sessions441


@preview_app.get("/security")
def secondary_security_page441(request: Request):
    require_preview()
    if request.query_params:
        raise HTTPException(400, "Unsupported query parameters")
    raw = request.cookies.get(COOKIE)
    uid = _session_user(raw)
    if uid is None:
        return RedirectResponse("/secondary/login", status_code=303)
    try:
        report = session_overview441(raw)
    except (PermissionError, RuntimeError, ValueError, sqlite3.Error, OSError):
        raise HTTPException(503, "Secondary session details unavailable") from None

    csrf = issue_token(load_key())
    html = f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="referrer" content="no-referrer">
<title>Session Security · Tracker DEV</title>
<style>
*{{box-sizing:border-box}}
body{{font:16px system-ui,sans-serif;max-width:550px;margin:auto;padding:16px}}
section{{border:1px solid #9995;border-radius:12px;padding:16px;margin:16px 0}}
button{{font:inherit;min-height:46px;width:100%;padding:12px}}
p{{line-height:1.5}}
</style></head><body><main>
<h1>Session Security</h1>
<p>Private workspace {uid} · DEV-only pilot</p>
<p><a href="/secondary/overview">Overview</a> ·
<a href="/secondary/readiness">Readiness</a></p>
<section>
<h2>Active Sessions</h2>
<p>{report["active_sessions"]} active session(s), including this device.</p>
<p>{report["other_sessions"]} other active session(s).</p>
<p>Current session expires {escape(report["current_expires_utc"])}.</p>
<form method="post" action="/secondary/security/revoke-others">
<input type="hidden" name="csrf_token" value="{escape(csrf, quote=True)}">
<button type="submit">Sign Out Other Devices</button>
</form>
</section>
<p>Session revocation does not change the password, enable standard
Tracker login, or modify any private health or inventory records.
Sign out this device from the Overview page.</p>
</main></body></html>'''
    return _csrf_response(
        HTMLResponse(html, headers={"Cache-Control": "no-store"}),
        csrf,
    )


@preview_app.post("/security/revoke-others")
async def secondary_revoke_others441(request: Request):
    require_preview()
    if request.query_params:
        raise HTTPException(400, "Unsupported query parameters")
    raw = request.cookies.get(COOKIE)
    uid = _session_user(raw)
    if uid is None:
        raise HTTPException(401, "Secondary session required")

    form = await request.form()
    _csrf_check(request, form)
    if set(form) != {"csrf_token"} or len(form.getlist("csrf_token")) != 1:
        raise HTTPException(422, "Unexpected session control fields")

    try:
        revoke_other_sessions441(raw)
    except PermissionError:
        raise HTTPException(401, "Secondary session expired") from None
    except (RuntimeError, ValueError, sqlite3.Error, OSError):
        raise HTTPException(503, "Secondary session revocation unavailable") from None

    return RedirectResponse(
        "/secondary/security", status_code=303,
        headers={"Cache-Control": "no-store"},
    )
