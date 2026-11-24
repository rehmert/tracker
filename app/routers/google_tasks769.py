"""Google Tasks OAuth connection and user-controlled sync settings (Release 769)."""
import secrets
from datetime import datetime, timedelta
from urllib.parse import quote

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import config
from ..google_tasks_client769 import (
    GoogleTasksError769, authorization_url769, configured769, token_exchange769,
)
from ..google_tasks_models769 import (
    GoogleTasksConnection769, GoogleTasksExclusion769, GoogleTasksLink769,
    GoogleTasksTitle773,
)
from ..google_tasks_projection769 import KINDS
from ..google_tasks_sync769 import connection769, sync_once769
from ..models import Protocol, RegimenSchedule
from ..scoped_db390 import get_scoped_db390
from ..templating import render

router = APIRouter()
BASE = "/integrations/google-tasks"


def _notice(message, *, error=False):
    return RedirectResponse(BASE + ("?err=" if error else "?msg=") +
                            quote(str(message), safe=""), status_code=303)


@router.get(BASE)
def settings769(request: Request, db: Session = Depends(get_scoped_db390)):
    conn = db.get(GoogleTasksConnection769, 1)
    exclusions = {(x.kind, x.source_id) for x in db.scalars(select(GoogleTasksExclusion769))}
    title_overrides = {
        (x.kind, x.source_id): x.title for x in db.scalars(select(GoogleTasksTitle773))
    }
    schedules = list(db.scalars(select(RegimenSchedule).order_by(RegimenSchedule.id)))
    # Only active protocols are eligible for Google Tasks publishing controls.
    protocols = list(db.scalars(
        select(Protocol).where(Protocol.is_active.is_(True)).order_by(Protocol.id)
    ))
    sources = []
    for schedule in schedules:
        if schedule.item and schedule.item.kind in KINDS:
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
    pending = list(db.scalars(
        select(GoogleTasksLink769).where(
            GoogleTasksLink769.kind == "protocol",
            GoogleTasksLink769.last_status == "completed",
        ).order_by(GoogleTasksLink769.scheduled_on.desc()).limit(30)
    ))
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
