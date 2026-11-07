"""Release 491: opt-in private dose and food forms for primary-page preview.

The existing session-authenticated secondary gateway selects the account.
This module delegates writes to the proven private dose (434) and food
(456) routes, with their CSRF, strict validation, and replay protection.
It never accepts a database path or user ID from a browser.
"""

import os
import sqlite3
from datetime import date, datetime
from html import escape
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse

router = APIRouter()


def _shared_enabled491():
    from .secondary_preview430 import preview_enabled
    return (
        preview_enabled()
        and os.getenv("TRACKER_FULLAPP_GATEWAY486", "0") == "1"
        and os.getenv("TRACKER_FULLAPP_WRITES488", "0") == "1"
    )


def dose_enabled491():
    from .secondary_preview430 import dose_writes_enabled434
    return (
        _shared_enabled491()
        and os.getenv("TRACKER_FULLAPP_DOSE_WRITES491", "0") == "1"
        and dose_writes_enabled434()
    )


def food_enabled491():
    from .secondary_preview430 import food_writes_enabled456
    return (
        _shared_enabled491()
        and os.getenv("TRACKER_FULLAPP_FOOD_WRITES491", "0") == "1"
        and food_writes_enabled456()
    )


def _new_csrf491():
    from .csrf_runtime import load_key
    from .csrf_tokens import issue_token
    return issue_token(load_key())


def _hidden491(csrf, nonce):
    return (
        '<input type="hidden" name="csrf_token" value="'
        + escape(csrf, quote=True) + '">'
        '<input type="hidden" name="submission_token" value="'
        + escape(nonce, quote=True) + '">'
    )


def dose_form491(uid):
    if type(uid) is not int or uid <= 1 or not dose_enabled491():
        raise HTTPException(404, "Private dose form unavailable")

    from .worker_dose_write434 import request_dose434
    from .routers.doses import INJECTION_SITES

    try:
        result = request_dose434(uid, "options")
    except (RuntimeError, ValueError, PermissionError, OSError, sqlite3.Error):
        raise HTTPException(503, "Private vials unavailable") from None

    if result.get("user_id") != uid or result.get("status") != "options":
        raise HTTPException(503, "Private dose inventory mismatch")

    options = result["items"]
    choices = []
    for item in options:
        if type(item["id"]) is not int or type(item["label"]) is not str:
            raise HTTPException(503, "Invalid private vial option")
        choices.append(
            '<option value="' + str(item["id"]) + '">'
            + escape(item["label"])
            + " · " + escape(
                f'{item["remaining_base"]:g} {item["base_unit"]} available'
            )
            + '</option>'
        )
    if not choices:
        choices = ['<option value="">No eligible vials</option>']

    sites = '<option value="">Not recorded</option>' + "".join(
        '<option value="' + escape(site, quote=True) + '">'
        + escape(site) + '</option>'
        for site in INJECTION_SITES
    )
    units = "".join(
        '<option value="' + escape(unit) + '"'
        + (' selected' if unit == 'mg' else '') + '>'
        + escape(unit) + '</option>'
        for unit in ("mg", "mcg", "IU", "mL", "uL", "g")
    )
    csrf = _new_csrf491()
    when = datetime.now().strftime("%Y-%m-%dT%H:%M")
    disabled = ' disabled' if not options else ''
    form = (
        '<section><h2>Log private dose</h2>'
        '<p>Choose the actual vial, amount, and unit. Only recorded '
        'administration is stored; this form does not recommend a dose.</p>'
        '<form method="post" action="/secondary/full/doses" autocomplete="off">'
        + _hidden491(csrf, str(uuid4()))
        + '<label>Vial<select name="vial_id" required>'
        + ''.join(choices) + '</select></label>'
        '<label>Administered at<input type="datetime-local" '
        'name="taken_at" value="' + escape(when, quote=True)
        + '" required></label>'
        '<label>Amount<input type="number" name="amount" '
        'min="0" step="any" inputmode="decimal" required></label>'
        '<label>Unit<select name="unit">' + units + '</select></label>'
        '<label>Injection site<select name="site">' + sites + '</select></label>'
        '<label>Notes<textarea name="notes" rows="3" maxlength="2000">'
        '</textarea></label>'
        '<button type="submit"' + disabled + '>Record dose</button>'
        '</form></section>'
    )
    return form, csrf


def food_forms491():
    if not food_enabled491():
        raise HTTPException(404, "Private food forms unavailable")

    from .secondary_nutrients463 import MACROS, MICROS
    csrf = _new_csrf491()
    today = date.today().isoformat()

    macros = "".join(
        '<label>' + escape(label) + ' (' + escape(unit) + ')'
        '<input type="number" min="0" step="0.001" inputmode="decimal" '
        'name="' + escape(key, quote=True) + '" '
        'placeholder="Unknown"></label>'
        for key, label, unit in MACROS
    )
    micros = "".join(
        '<label>' + escape(label) + ' (' + escape(unit) + ')'
        '<input type="number" min="0" step="0.001" inputmode="decimal" '
        'name="' + escape(key, quote=True) + '" '
        'placeholder="Unknown"></label>'
        for key, label, unit in MICROS
    )
    meals = "".join(
        '<option value="' + escape(meal) + '">'
        + escape(meal) + '</option>'
        for meal in ("Breakfast", "Lunch", "Dinner", "Snack")
    )

    water = (
        '<section><h2>Log water</h2>'
        '<form method="post" action="/secondary/full/food/water" '
        'autocomplete="off">'
        + _hidden491(csrf, str(uuid4()))
        + '<label>Date<input name="day" type="date" value="'
        + today + '" required></label>'
        '<label>Fluid ounces<input name="ounces" type="number" '
        'min="0.001" max="256" step="0.001" '
        'inputmode="decimal" required></label>'
        '<button type="submit">Save water</button></form></section>'
    )
    food = (
        '<section><h2>Log food</h2>'
        '<p>Enter known nutrient values per serving; leave unknown '
        'nutrients blank rather than entering zero.</p>'
        '<form method="post" action="/secondary/full/food/entry" '
        'autocomplete="off">'
        + _hidden491(csrf, str(uuid4()))
        + '<label>Date<input name="day" type="date" value="'
        + today + '" required></label>'
        '<label>Food name<input name="name" maxlength="160" required></label>'
        '<label>Meal<select name="meal">' + meals + '</select></label>'
        '<label>Servings<input name="servings" type="number" '
        'min="0.001" max="100" step="0.001" '
        'inputmode="decimal" value="1" required></label>'
        + macros
        + '<details><summary>Optional micronutrients</summary>'
        + micros + '</details>'
        '<button type="submit">Save food</button></form></section>'
    )
    return water + food, csrf


@router.post("/full/doses")
async def primary_dose_submit491(request: Request):
    if not dose_enabled491():
        raise HTTPException(404, "Private dose logging disabled")
    if request.url.path != "/secondary/full/doses" or request.query_params:
        raise HTTPException(400, "Unexpected private dose parameters")

    from .secondary_preview430 import dose_submit434
    result = await dose_submit434(request)
    if result.status_code != 303:
        raise HTTPException(503, "Private dose recording failed")

    return RedirectResponse(
        "/secondary/full/doses", status_code=303,
        headers={"Cache-Control": "no-store"},
    )


async def _food_submit491(request, action):
    if not food_enabled491():
        raise HTTPException(404, "Private food logging disabled")

    if (
        request.url.path != "/secondary/full/food/" + action
        or request.query_params
    ):
        raise HTTPException(400, "Unexpected private food parameters")

    from .secondary_preview430 import _secondary_food_submit456
    from .worker_food452 import validate_day452

    result = await _secondary_food_submit456(request, action)
    if result.status_code != 303:
        raise HTTPException(503, "Private food logging failed")

    # The delegated worker has already validated this exact form.
    form = await request.form()
    day = validate_day452(str(form.get("day", "")))
    return RedirectResponse(
        "/secondary/full/food?day=" + day,
        status_code=303,
        headers={"Cache-Control": "no-store"},
    )


@router.post("/full/food/water")
async def primary_water_submit491(request: Request):
    return await _food_submit491(request, "water")


@router.post("/full/food/entry")
async def primary_food_submit491(request: Request):
    return await _food_submit491(request, "food")
