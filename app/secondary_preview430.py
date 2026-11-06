"""DEV-only, explicitly enabled secondary-user preview and vitals pilot.

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
<p>DEV only · Read-only overview</p>
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
<p>DEV-only read-only preview. Account {uid}.</p>
<p><a href="/secondary/vitals">Recent Vitals</a> ·
<a href="/secondary/doses">Recent Doses</a> ·
<a href="/secondary/inventory">My Inventory</a></p>
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
