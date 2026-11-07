"""Release 489: single private vial-creation form for the primary preview.

This reuses the separately gated Release 435 worker, CSRF handling and
idempotency validation. The authenticated secondary session selects the
workspace; no browser-provided user or database path is accepted. Other
primary-app writes remain unavailable.
"""

import os
import sqlite3
from html import escape
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse

router = APIRouter()


def vial_writes_enabled489():
    from .secondary_preview430 import (
        inventory_writes_enabled435, preview_enabled,
    )

    return (
        preview_enabled()
        and os.getenv("TRACKER_FULLAPP_GATEWAY486", "0") == "1"
        and os.getenv("TRACKER_FULLAPP_WRITES488", "0") == "1"
        and os.getenv("TRACKER_FULLAPP_VIAL_WRITES489", "0") == "1"
        and inventory_writes_enabled435()
    )


def vial_form489(uid):
    """Build a signed form using independently verified private inventory."""
    from .csrf_runtime import load_key
    from .csrf_tokens import issue_token
    from .units import CONTENT_UNITS
    from .models import VIAL_FORMS
    from .worker_inventory435 import request_inventory435

    if type(uid) is not int or uid <= 1 or not vial_writes_enabled489():
        raise HTTPException(404, "Private vial creation unavailable")

    try:
        report = request_inventory435(uid, "inventory")
    except (RuntimeError, OSError, ValueError, PermissionError, sqlite3.Error):
        raise HTTPException(503, "Private compound choices unavailable") from None

    if (
        report.get("user_id") != uid
        or report.get("status") != "inventory"
        or type(report.get("compounds")) is not list
    ):
        raise HTTPException(503, "Private inventory identity mismatch")

    choices = []
    for item in report["compounds"]:
        if (
            type(item) is not dict
            or type(item.get("id")) is not int
            or not 0 < item["id"] < 2147483648
            or type(item.get("name")) is not str
            or not 0 < len(item["name"]) <= 120
        ):
            raise HTTPException(503, "Invalid private compound option")
        choices.append(
            '<option value="' + str(item["id"]) + '">'
            + escape(item["name"]) + '</option>'
        )

    units = "".join(
        '<option value="' + escape(unit, quote=True) + '"'
        + (' selected' if unit == 'mg' else '') + '>'
        + escape(unit) + '</option>'
        for unit in sorted(CONTENT_UNITS)
    )
    forms = "".join(
        '<option value="' + escape(form, quote=True) + '">'
        + escape(form.title()) + '</option>'
        for form in sorted(VIAL_FORMS)
    )
    csrf = issue_token(load_key())
    nonce = str(uuid4())
    disabled = " disabled" if not choices else ""

    html = (
        '<section><h2>Add one private vial</h2>'
        '<p>This records one sealed vial without a purchase record. '
        'Choose a unit compatible with its compound.</p>'
        '<form method="post" action="/secondary/full/vials" autocomplete="off">'
        '<input type="hidden" name="csrf_token" value="'
        + escape(csrf, quote=True) + '">'
        '<input type="hidden" name="submission_token" value="'
        + escape(nonce, quote=True) + '">'
        '<label>Compound <select name="compound_id" required>'
        + "".join(choices) + '</select></label>'
        '<label>Label <input name="label" maxlength="160"></label>'
        '<label>Content <input name="content_value" type="number" '
        'min="0.000001" step="any" inputmode="decimal" required></label>'
        '<label>Unit <select name="content_unit">'
        + units + '</select></label>'
        '<label>Form <select name="form">' + forms + '</select></label>'
        '<label>Liquid volume (mL) <input name="volume_ml" '
        'type="number" min="0.0001" step="any" inputmode="decimal" '
        'placeholder="Required for solutions"></label>'
        '<label>Lot <input name="lot" maxlength="80"></label>'
        '<label>Cap color <input name="cap_color" maxlength="60"></label>'
        '<label>Notes <textarea name="notes" maxlength="2000"></textarea>'
        '</label>'
        '<button type="submit"' + disabled + '>Add vial</button>'
        '</form></section>'
    )
    return html, csrf


@router.post("/full/vials")
async def primary_vial_create489(request: Request):
    if not vial_writes_enabled489():
        raise HTTPException(404, "Private primary vial write unavailable")

    if (
        request.url.path != "/secondary/full/vials"
        or request.query_params
    ):
        raise HTTPException(400, "Unexpected private write parameters")

    from .secondary_preview430 import _inventory_submit435

    result = await _inventory_submit435(request, "create_vial")
    if result.status_code != 303:
        raise HTTPException(503, "Private vial creation failed")

    return RedirectResponse(
        "/secondary/full/vials",
        status_code=303,
        headers={"Cache-Control": "no-store"},
    )
