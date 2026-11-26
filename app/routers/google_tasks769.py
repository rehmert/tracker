"""Google Tasks OAuth connection and user-controlled sync settings (Release 769)."""
import re
import secrets
from datetime import datetime, timedelta
from urllib.parse import quote

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import config
from ..csrf_runtime import FIELD_NAME as CSRF_FIELD_NAME
from ..google_tasks_client769 import (
    GoogleTasksError769, authorization_url769, configured769, token_exchange769,
)
from ..google_tasks_models769 import (
    GoogleTasksConnection769, GoogleTasksExclusion769, GoogleTasksLink769,
    GoogleTasksTitle773,
)
from ..google_tasks_projection769 import KINDS
from ..google_tasks_sync769 import connection769, sync_once769
from ..google_protocol_review783 import review_rows783, reconcile_choice783
from ..inventory_lock import require_inventory_write
from ..models import Protocol, RegimenSchedule
from ..scoped_db390 import get_scoped_db390
from ..templating import render

router = APIRouter()
BASE = "/integrations/google-tasks"


def _notice(message, *, error=False):
    return RedirectResponse(BASE + ("?err=" if error else "?msg=") +
                            quote(str(message), safe=""), status_code=303)



def _title_sources774(db: Session):
    """Use identical source visibility for bulk editing and the settings page."""
    schedules = list(db.scalars(select(RegimenSchedule).order_by(RegimenSchedule.id)))
    protocols = list(db.scalars(
        select(Protocol).where(Protocol.is_active.is_(True)).order_by(Protocol.id)
    ))
    return schedules, protocols


@router.get(BASE)
def settings769(request: Request, db: Session = Depends(get_scoped_db390)):
    conn = db.get(GoogleTasksConnection769, 1)
    exclusions = {(x.kind, x.source_id) for x in db.scalars(select(GoogleTasksExclusion769))}
    title_overrides = {
        (x.kind, x.source_id): x.title for x in db.scalars(select(GoogleTasksTitle773))
    }
    # Only active protocols are eligible for Google Tasks publishing controls.
    schedules, protocols = _title_sources774(db)
    sources = []
    for schedule in schedules:
        if schedule.item and schedule.item.kind in ("medication", "supplement"):
            sources.append({
                "kind": schedule.item.kind, "id": schedule.id,
                "name": schedule.item.name, "detail": schedule.amount,
                "active": schedule.active and schedule.item.active,
                "excluded": (schedule.item.kind, schedule.id) in exclusions,
                "custom_title": title_overrides.get((schedule.item.kind, schedule.id), ""),
            })
    for protocol in protocols:
        for item in protocol.items:
            sources.append({
                "kind": "protocol", "id": item.id,
                "name": protocol.name + " / " + item.compound.name,
                "detail": f"{item.amount_value:g} {item.amount_unit}",
                "active": protocol.is_active,
                "excluded": ("protocol", item.id) in exclusions,
                "custom_title": title_overrides.get(("protocol", item.id), ""),
            })
    pending = review_rows783(db)
    return render(
        request, "google_tasks769.html",
        configured=configured769() is not None,
        connected=bool(conn and conn.refresh_token),
        enabled=bool(conn and conn.enabled),
        last_sync=conn.last_sync_at if conn else None,
        last_error=conn.last_error if conn else "",
        sources=sources, pending=pending,
        instance=config.instance_label(),
        production_access=config.instance_label() == "PROD",
    )


@router.post(BASE + "/connect")
def begin_connect769(db: Session = Depends(get_scoped_db390)):
    if config.instance_label() != "PROD":
        return _notice("DEV cannot connect to Google Tasks.", error=True)
    if not configured769():
        return _notice("Configure the private Google OAuth client settings on this host first.", error=True)
    conn = connection769(db)
    state = secrets.token_urlsafe(32)
    conn.oauth_state = state
    conn.oauth_state_at = datetime.utcnow()
    db.commit()
    return RedirectResponse(authorization_url769(state), status_code=303)


@router.get(BASE + "/callback")
def callback769(state: str = "", code: str = "", error: str = "",
                db: Session = Depends(get_scoped_db390)):
    if config.instance_label() != "PROD":
        raise HTTPException(403, "Google authorization is disabled outside PROD")
    conn = db.get(GoogleTasksConnection769, 1)
    valid = bool(conn and state and secrets.compare_digest(conn.oauth_state or "", state)
                 and conn.oauth_state_at
                 and datetime.utcnow() - conn.oauth_state_at < timedelta(minutes=10))
    if not valid:
        raise HTTPException(400, "Google authorization state invalid or expired")
    conn.oauth_state, conn.oauth_state_at = "", None
    db.commit()
    if error or not code:
        return _notice("Google authorization was not granted.", error=True)
    try:
        token = token_exchange769({"grant_type": "authorization_code", "code": code})
    except GoogleTasksError769:
        return _notice("Google authorization failed. Retry connecting.", error=True)
    if not token.get("refresh_token"):
        return _notice("Google did not issue offline access. Revoke the old consent and reconnect.", error=True)
    conn.refresh_token = token["refresh_token"]
    conn.enabled = True
    conn.last_error = ""
    db.commit()
    return _notice("Google Tasks connected. Sync is enabled; run Sync now to populate tasks.")


@router.post(BASE + "/enabled")
def set_enabled769(enabled: str = Form(""),
                   db: Session = Depends(get_scoped_db390)):
    conn = db.get(GoogleTasksConnection769, 1)
    if not conn or not conn.refresh_token:
        return _notice("Connect Google Tasks first.", error=True)
    conn.enabled = enabled == "yes"
    db.commit()
    return _notice("Google Tasks sync " + ("enabled." if conn.enabled else "paused."))


@router.post(BASE + "/source/{kind}/{source_id}")
def toggle_source769(kind: str, source_id: int,
                     db: Session = Depends(get_scoped_db390)):
    if kind not in KINDS or source_id < 1:
        raise HTTPException(404)
    if kind == "protocol":
        from ..models import ProtocolItem
        if db.get(ProtocolItem, source_id) is None:
            raise HTTPException(404)
    else:
        schedule = db.get(RegimenSchedule, source_id)
        if not schedule or schedule.item.kind != kind:
            raise HTTPException(404)
    row = db.scalar(select(GoogleTasksExclusion769).where(
        GoogleTasksExclusion769.kind == kind,
        GoogleTasksExclusion769.source_id == source_id,
    ))
    if row is None:
        db.add(GoogleTasksExclusion769(kind=kind, source_id=source_id))
        value = "excluded"
    else:
        db.delete(row)
        value = "included"
    db.commit()
    return _notice("Schedule " + value + " in future Google Tasks sync.")



@router.post(BASE + "/titles")
async def save_all_titles774(request: Request, db: Session = Depends(get_scoped_db390)):
    """Validate the complete visible form, then commit every title in one transaction.

    A changed source list (such as deactivation while the page was open)
    rejects the stale form rather than silently dropping or deleting titles.
    """
    schedules, protocols = _title_sources774(db)
    editable = {
        (schedule.item.kind, schedule.id)
        for schedule in schedules
        if schedule.item and schedule.item.kind in ("medication", "supplement")
    }
    editable.update(
        ("protocol", item.id)
        for protocol in protocols
        for item in protocol.items
    )

    form = await request.form()
    titles = {}
    csrf_fields = 0
    for field, value in form.multi_items():
        # The shared Tracker browser form enhancer injects csrf_token into
        # all POST forms. Central middleware verifies this token; it is not
        # a user-editable title, nor an unknown/forged title field.
        if field == CSRF_FIELD_NAME:
            csrf_fields += 1
            if csrf_fields > 1 or not isinstance(value, str):
                raise HTTPException(400, "Duplicate or invalid CSRF form field")
            continue
        match = re.fullmatch(r"title_(medication|supplement|protocol)_([1-9][0-9]*)", field)
        if not match or not isinstance(value, str):
            raise HTTPException(400, "Unexpected Google Tasks title field")
        key = (match.group(1), int(match.group(2)))
        if key in titles:
            raise HTTPException(400, "Duplicate Google Tasks title field")
        if any(ord(ch) < 32 or ord(ch) == 127 for ch in value):
            raise HTTPException(400, "Google Tasks titles must be one line")
        cleaned = " ".join(value.split())
        if len(cleaned) > 80:
            raise HTTPException(400, "Google Tasks titles must be 80 characters or less")
        titles[key] = cleaned

    if set(titles) != editable:
        raise HTTPException(409, "Schedules changed; reload Google Tasks settings and retry")

    existing = {
        (row.kind, row.source_id): row
        for row in db.scalars(select(GoogleTasksTitle773))
    }
    changed = 0
    for key, cleaned in titles.items():
        row = existing.get(key)
        if not cleaned:
            if row is not None:
                db.delete(row)
                changed += 1
        elif row is None:
            db.add(GoogleTasksTitle773(kind=key[0], source_id=key[1], title=cleaned))
            changed += 1
        elif row.title != cleaned:
            row.title = cleaned
            changed += 1

    db.commit()
    return _notice(
        f"Saved {changed} Google Tasks title change(s). "
        "Existing open tasks update on the next sync."
    )


@router.post(BASE + "/title/{kind}/{source_id}")
def update_title773(kind: str, source_id: int, title: str = Form(""),
                    db: Session = Depends(get_scoped_db390)):
    """Save a per-schedule Google-only name; blank restores default formatting."""
    if kind not in KINDS or source_id < 1:
        raise HTTPException(404)
    if kind == "protocol":
        from ..models import ProtocolItem
        item = db.get(ProtocolItem, source_id)
        if not item or not item.protocol or not item.protocol.is_active:
            raise HTTPException(404)
    else:
        schedule = db.get(RegimenSchedule, source_id)
        if not schedule or not schedule.item or schedule.item.kind != kind:
            raise HTTPException(404)
    if any(ord(ch) < 32 or ord(ch) == 127 for ch in title):
        raise HTTPException(400, "Google Tasks title must be one line")
    cleaned = " ".join(title.split())
    if len(cleaned) > 80:
        raise HTTPException(400, "Google Tasks title must be 80 characters or less")
    row = db.scalar(select(GoogleTasksTitle773).where(
        GoogleTasksTitle773.kind == kind,
        GoogleTasksTitle773.source_id == source_id,
    ))
    if not cleaned:
        if row is not None:
            db.delete(row)
        message = "Default Google Tasks title restored."
    else:
        if row is None:
            db.add(GoogleTasksTitle773(kind=kind, source_id=source_id,
                                       title=cleaned))
        else:
            row.title = cleaned
        message = "Custom Google Tasks title saved."
    db.commit()
    return _notice(message + " Existing open tasks update at next sync.")

@router.post(BASE + "/sync")
def run_sync769(db: Session = Depends(get_scoped_db390)):
    if config.instance_label() != "PROD":
        return _notice("DEV cannot synchronize with Google Tasks.", error=True)
    db.rollback()
    try:
        result = sync_once769()
    except GoogleTasksError769 as exc:
        return _notice(str(exc), error=True)
    if result["status"] != "ok":
        return _notice("Sync not started: " + result["status"], error=True)
    return _notice(
        f"Synced. Created {result['created']} tasks; imported "
        f"{result['imported']} regimen completions; "
        f"{result['pending_protocols']} protocol completions pending inventory review."
    )


@router.post(BASE + "/disconnect")
def disconnect769(db: Session = Depends(get_scoped_db390)):
    conn = db.get(GoogleTasksConnection769, 1)
    if conn:
        conn.refresh_token, conn.enabled, conn.oauth_state = "", False, ""
        conn.oauth_state_at = None
        db.commit()
    return _notice("Google Tasks disconnected locally. Existing Google tasks were not deleted.")


@router.post(BASE + "/reconcile")
async def reconcile_protocols783(request: Request, db: Session = Depends(get_scoped_db390)):
    """Confirm selected rows as one atomic transaction; no Google API writes."""
    form = await request.form()
    if form.get("confirm") != "yes" or len(form.getlist("confirm")) != 1:
        raise HTTPException(400, "Confirm the selected actual administrations first.")
    origin = form.get("return_to", "")
    if origin not in ("", "today") or len(form.getlist("return_to")) > 1:
        raise HTTPException(400, "Invalid return destination.")
    back = "/mobile" if origin == "today" else "/calendar"
    choices = {}
    times = {}
    for field, value in form.multi_items():
        if field in (CSRF_FIELD_NAME, "confirm", "return_to"):
            continue
        target = choices if field.startswith("choice_") else times if field.startswith("when_") else None
        key = field.split("_", 1)[-1]
        if target is None or key in target or not isinstance(value, str) or len(key) > 180 or len(value) > 80:
            raise HTTPException(400, "Invalid reconciliation form.")
        target[key] = value
    selected = [(key, choice) for key, choice in choices.items() if choice]
    if not selected or len(selected) > 100 or set(times) - set(choices):
        raise HTTPException(400, "Select 1–100 administrations for review.")
    require_inventory_write(db)
    try:
        for key, choice in selected:
            reconcile_choice783(db, key, choice, times.get(key, ""))
        db.commit()
    except ValueError as exc:
        db.rollback()
        return RedirectResponse(back + "?review_error=" + quote(str(exc), safe="") +
                                "#google-protocol-review783", status_code=303)
    return RedirectResponse(back + "?review_saved=" + str(len(selected)) +
                            "#google-protocol-review783", status_code=303)
