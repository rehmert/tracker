"""Release 487: opt-in DEV secondary GET-only, inert primary-page preview.

The browser never selects user IDs, worker credentials, database paths or
an upstream HTTP origin. Every request is authorized against the server's
secondary session, then dispatched to a short-lived isolated Python process
using an allowlisted JSON request. The child snapshots the private database;
no live user records are modified. No interactive forms or scripts are
returned, and no secondary route is available on PROD.
"""

import json
from datetime import date
import os
import sqlite3
import subprocess
import sys
from html import escape
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from .fullapp_gateway486 import authorize_fullapp_route486
from .worker_scope428 import SOURCE_ROOT, worker_environment428

router = APIRouter()
MAX_WORKER_OUTPUT487 = 65536


def _page_query487(request, route):
    allowed = (
        {"day"} if route == "/food"
        else {"q"} if route == "/compounds"
        else set()
    )
    given = list(request.query_params.multi_items())
    if (
        len(given) > 1
        or any(key not in allowed for key, _ in given)
        or any(len(value) > 96 for _, value in given)
    ):
        raise HTTPException(400, "Unsupported private page parameters")

    query = dict(given)
    if "day" in query:
        try:
            if date.fromisoformat(query["day"]).isoformat() != query["day"]:
                raise ValueError("Invalid day format")
        except ValueError:
            raise HTTPException(400, "Invalid food day") from None
    return query


def _run_isolated_page487(plan, query):
    try:
        env = worker_environment428(plan.user_id)
    except (OSError, PermissionError, ValueError, RuntimeError, sqlite3.Error):
        raise HTTPException(
            503, "Private worker unavailable"
        ) from None

    request = json.dumps(
        {"route": plan.route, "query": query},
        separators=(",", ":"),
    )

    if len(request) > 2048:
        raise HTTPException(400, "Private page parameters too long")

    try:
        result = subprocess.run(
            [sys.executable, "-m", "app.worker_page487"],
            cwd=SOURCE_ROOT,
            env=env,
            input=request,
            capture_output=True,
            text=True,
            timeout=70,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        raise HTTPException(
            503, "Private page worker unavailable"
        ) from None

    if (
        result.returncode != 0
        or not result.stdout
        or len(result.stdout) > MAX_WORKER_OUTPUT487
    ):
        # Do not return private worker stderr, file paths or credentials.
        raise HTTPException(503, "Private page could not be displayed")

    try:
        data = json.loads(result.stdout)
    except (TypeError, ValueError):
        raise HTTPException(503, "Invalid private worker response") from None

    if (
        type(data) is not dict
        or set(data) != {
            "mode", "user_id", "route", "page_status",
            "inert_text", "snapshot_only", "network_listener",
        }
        or data["mode"] != "private-page-snapshot487"
        or data["user_id"] != plan.user_id
        or data["route"] != plan.route
        or data["page_status"] != 200
        or data["snapshot_only"] is not True
        or data["network_listener"] is not False
        or type(data["inert_text"]) is not str
        or not data["inert_text"]
        or len(data["inert_text"]) > 18000
    ):
        raise HTTPException(503, "Private page worker identity mismatch")

    return data["inert_text"]


@router.get("/full/{path:path}")
def preview_primary_page487(request: Request, path: str):
    """Render inert text from a private snapshot. NO live POST/asset proxy."""
    plan = authorize_fullapp_route486(request, path)
    query = _page_query487(request, plan.route)
    content = _run_isolated_page487(plan, query)

    links = (
        ("/", "Dashboard"), ("/compounds", "Compounds"),
        ("/vials", "Vials"), ("/labs", "Labs"),
        ("/protocols", "Protocols"), ("/doses", "Doses"),
        ("/vitals", "Vitals"), ("/food", "Food"),
    )
    nav = " ".join(
        '<a href="/secondary/full'
        + (path if path != "/" else "/")
        + '">' + escape(label) + "</a>"
        for path, label in links
    )

    form_html, csrf = _compound_form488() if (
        plan.route == "/compounds" and _compound_write_enabled488()
    ) else ("", None)
    form_policy = "form-action 'self'" if csrf else "form-action 'none'"

    html = (
        '<!doctype html><html lang="en"><head>'
        '<meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<title>Private Tracker Read-only Preview</title>'
        '<style>body{font:16px/1.5 system-ui;max-width:900px;'
        'margin:auto;padding:16px;color:#172535}'
        'nav{display:flex;gap:12px;flex-wrap:wrap;margin:14px 0}'
        'a{color:#14599c}pre{white-space:pre-wrap;overflow-wrap:anywhere;'
        'background:#f5f7fa;border:1px solid #dde4ec;'
        'padding:16px;border-radius:8px}</style>'
        '</head><body><main>'
        '<a href="/secondary/overview">Private workspace</a>'
        '<h1>Primary Tracker — read-only preview</h1>'
        '<p>Snapshot of your private workspace. Original app links '
        'are disabled. Compound creation is available below only '
        'when the separate private write gate is enabled.</p>'
        '<nav aria-label="Private features">' + nav + '</nav>'
        '<h2>' + escape(plan.route) + '</h2>'
        '<pre>' + escape(content) + '</pre>' + form_html
        + '</main></body></html>'
    )

    response = HTMLResponse(
        html,
        headers={
            "Cache-Control": "no-store",
            "Content-Security-Policy": (
                "default-src 'none'; style-src 'unsafe-inline'; "
                "base-uri 'none'; " + form_policy + "; frame-ancestors 'none'"
            ),
            "X-Content-Type-Options": "nosniff",
            "Referrer-Policy": "no-referrer",
        },
    )
    if csrf:
        from .secondary_preview430 import _csrf_response
        return _csrf_response(response, csrf)
    return response


def _compound_write_enabled488():
    """New primary-view form is separately opt-in. Pilot writes unchanged."""
    from .secondary_preview430 import (
        inventory_writes_enabled435, preview_enabled,
    )
    return (
        preview_enabled()
        and os.getenv("TRACKER_FULLAPP_GATEWAY486", "0") == "1"
        and os.getenv("TRACKER_FULLAPP_WRITES488", "0") == "1"
        and inventory_writes_enabled435()
    )


def _compound_form488():
    """Only the existing verified inventory writer receives this POST."""
    from .csrf_runtime import load_key
    from .csrf_tokens import issue_token
    from .models import CATEGORIES
    from .units import CONTENT_UNITS

    csrf = issue_token(load_key())
    nonce = str(uuid4())
    categories = "".join(
        '<option value="' + escape(value, quote=True) + '">'
        + escape(value.title()) + "</option>"
        for value in sorted(CATEGORIES)
    )
    units = "".join(
        '<option value="' + escape(value, quote=True) + '">'
        + escape(value) + "</option>"
        for value in sorted(CONTENT_UNITS)
    )
    html = (
        '<section><h2>Add compound to my private inventory</h2>'
        '<p>This writes only to your authenticated private workspace.</p>'
        '<form method="post" action="/secondary/full/compounds" '
        'autocomplete="off">'
        '<input type="hidden" name="csrf_token" value="'
        + escape(csrf, quote=True) + '">'
        '<input type="hidden" name="submission_token" value="'
        + escape(nonce, quote=True) + '">'
        '<label>Compound name <input name="name" maxlength="120" '
        'required></label>'
        '<label>Category <select name="category">' + categories
        + '</select></label>'
        '<label>Default unit <select name="primary_unit">' + units
        + '</select></label>'
        '<label>Notes <textarea name="notes" maxlength="2000"></textarea>'
        '</label><button type="submit">Add compound</button>'
        '</form></section>'
    )
    return html, csrf


@router.post("/full/compounds")
async def primary_compound_create488(request: Request):
    """Signed-CSRF, deduplicated private write via existing Release 435 worker."""
    if not _compound_write_enabled488():
        raise HTTPException(404, "Private primary writes unavailable")
    if (
        request.url.path != "/secondary/full/compounds"
        or request.query_params
    ):
        raise HTTPException(400, "Unexpected private write parameters")
    from .secondary_preview430 import _inventory_submit435

    result = await _inventory_submit435(request, "create_compound")
    if result.status_code != 303:
        raise HTTPException(503, "Private inventory write failed")

    return RedirectResponse(
        "/secondary/full/compounds",
        status_code=303,
        headers={"Cache-Control": "no-store"},
    )
