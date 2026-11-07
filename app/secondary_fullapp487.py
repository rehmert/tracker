"""Release 487: opt-in DEV secondary GET-only, inert primary-page preview.

The browser never selects user IDs, worker credentials, database paths or
an upstream HTTP origin. Every request is authorized against the server's
secondary session, then dispatched to a short-lived isolated Python process
using an allowlisted JSON request. The child snapshots the private database;
no live user records are modified. No interactive forms or scripts are
returned, and no secondary route is available on PROD.
"""

import json
import os
import sqlite3
import subprocess
import sys
from html import escape

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse

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

    # Date/query validity is additionally checked by the child.
    return dict(given)


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
        '<p>Snapshot of your private workspace. This view is '
        'non-interactive; writes and original app links are disabled.</p>'
        '<nav aria-label="Private features">' + nav + '</nav>'
        '<h2>' + escape(plan.route) + '</h2>'
        '<pre>' + escape(content) + '</pre>'
        '</main></body></html>'
    )

    return HTMLResponse(
        html,
        headers={
            "Cache-Control": "no-store",
            "Content-Security-Policy": (
                "default-src 'none'; style-src 'unsafe-inline'; "
                "base-uri 'none'; form-action 'none'; frame-ancestors 'none'"
            ),
            "X-Content-Type-Options": "nosniff",
            "Referrer-Policy": "no-referrer",
        },
    )
