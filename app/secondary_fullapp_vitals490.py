"""Release 490: opt-in private vitals form on the primary-page preview.

Identity is selected by the existing secondary session; form processing,
CSRF, validation, idempotency, and DB writes remain in the proven 433
gateway and per-user worker. Nothing here opens the administrator engine.
"""

import os
from datetime import datetime
from html import escape
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse

router = APIRouter()


def vital_writes_enabled490():
    from .secondary_preview430 import preview_enabled, vital_writes_enabled433
    return (
        preview_enabled()
        and os.getenv("TRACKER_FULLAPP_GATEWAY486", "0") == "1"
        and os.getenv("TRACKER_FULLAPP_WRITES488", "0") == "1"
        and os.getenv("TRACKER_FULLAPP_VITAL_WRITES490", "0") == "1"
        and vital_writes_enabled433()
    )


def vital_form490():
    """Return HTML and signed CSRF token, never client-selected identity."""
    if not vital_writes_enabled490():
        raise HTTPException(404, "Private vitals form unavailable")

    from . import config
    from .csrf_runtime import load_key
    from .csrf_tokens import issue_token

    csrf = issue_token(load_key())
    nonce = str(uuid4())
    measured_at = datetime.now().strftime("%Y-%m-%dT%H:%M")
    weight_unit = config.WEIGHT_UNIT if config.WEIGHT_UNIT in ("lb", "kg") else "lb"
    alternate = "kg" if weight_unit == "lb" else "lb"
    html = (
        '<section aria-labelledby="vitals-form-title490">'
        '<h2 id="vitals-form-title490">Log private vitals</h2>'
        '<p>Save a weight, blood-pressure or pulse reading to your '
        'authenticated private workspace.</p>'
        '<form method="post" action="/secondary/full/vitals" autocomplete="off">'
        '<input type="hidden" name="csrf_token" value="'
        + escape(csrf, quote=True) + '">'
        '<input type="hidden" name="submission_token" value="'
        + escape(nonce, quote=True) + '">'
        '<label>Measured at <input type="datetime-local" name="measured_at" '
        'value="' + escape(measured_at, quote=True) + '" required></label>'
        '<label>Weight <input type="number" name="weight" '
        'step="0.01" min="0" inputmode="decimal"></label>'
        '<label>Weight unit <select name="weight_unit">'
        '<option value="' + escape(weight_unit) + '" selected>'
        + escape(weight_unit) + '</option>'
        '<option value="' + escape(alternate) + '">'
        + escape(alternate) + '</option></select></label>'
        '<label>Systolic <input type="number" name="systolic" '
        'min="50" max="300" inputmode="numeric"></label>'
        '<label>Diastolic <input type="number" name="diastolic" '
        'min="20" max="200" inputmode="numeric"></label>'
        '<label>Pulse (bpm) <input type="number" name="pulse_bpm" '
        'min="20" max="300" inputmode="numeric"></label>'
        '<label>Context <input name="context" maxlength="80" '
        'placeholder="Morning, seated"></label>'
        '<label>Notes <textarea name="notes" maxlength="2000" '
        'rows="3"></textarea></label>'
        '<p>Enter at least one of weight, blood pressure or pulse.</p>'
        '<button type="submit">Save vital reading</button>'
        '</form></section>'
    )
    return html, csrf


@router.post("/full/vitals")
async def primary_vital_submit490(request: Request):
    """Reuse signed 433 submission, then return to the private primary page."""
    if not vital_writes_enabled490():
        raise HTTPException(404, "Private primary vitals unavailable")
    if (
        request.url.path != "/secondary/full/vitals"
        or request.query_params
    ):
        raise HTTPException(400, "Unexpected private vitals parameters")

    from .secondary_preview430 import vital_submit433

    result = await vital_submit433(request)
    if result.status_code != 303:
        raise HTTPException(503, "Private vital write failed")

    return RedirectResponse(
        "/secondary/full/vitals",
        status_code=303,
        headers={"Cache-Control": "no-store"},
    )
