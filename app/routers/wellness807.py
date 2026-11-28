"""Workspace-scoped wellness and structured reaction mutations."""
from datetime import date, datetime, timedelta
import json

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..audit_helpers import record, snapshot
from ..inventory_lock import require_inventory_write
from ..models import BlendDose, DoseLog
from ..scoped_db390 import get_scoped_db390
from ..wellness_models807 import WellnessPreferences807, WellnessDay807, Symptom807, SiteReaction807
from ..wellness807 import (METRICS, SYMPTOMS, REACTIONS, checked_day, checked_notes,
                          metric_values, metric_order, saved_order, episode_values)

router = APIRouter()
DAY_FIELDS = ("day", "values_json", "notes")
EPISODE_FIELDS = ("severity", "onset_at", "resolved_at", "notes")
REACTION_FIELDS = ("dose_id", "blend_dose_id", "site", "reaction", *EPISODE_FIELDS)

def today_context807(db, raw_day="", symptom_id=0):
    try:
        day = checked_day(raw_day) if raw_day else date.today()
    except ValueError:
        day = date.today()
    order = saved_order(db.get(WellnessPreferences807, 1))
    row = db.scalar(select(WellnessDay807).where(WellnessDay807.day == day))
    recent = list(db.scalars(select(WellnessDay807).order_by(WellnessDay807.day.desc()).limit(30)))
    symptoms = list(db.scalars(select(Symptom807).order_by(Symptom807.onset_at.desc()).limit(30)))
    editing = db.get(Symptom807, symptom_id) if 0 < symptom_id <= 2**63-1 else None
    return dict(wellness_day=day, wellness_metrics=METRICS, wellness_order=order,
                wellness_row=row, wellness_values=json.loads(row.values_json) if row else {},
                wellness_recent=recent, wellness_symptoms=symptoms, wellness_symptom_types=SYMPTOMS,
                wellness_symptom_edit=editing, wellness_now=datetime.now().strftime("%Y-%m-%dT%H:%M"))

def _today(day=None, *, anchor="wellness807"):
    return RedirectResponse("/mobile" + (f"?wellness_day={day.isoformat()}" if day else "") + "#" + anchor, status_code=303)

def _bad(exc):
    raise HTTPException(422, str(exc))

@router.post("/wellness807/save")
async def save_wellness807(request: Request, db: Session = Depends(get_scoped_db390)):
    form = await request.form()
    require_inventory_write(db)
    try:
        day = checked_day(form.get("day"))
        order = saved_order(db.get(WellnessPreferences807, 1))
        row = db.scalar(select(WellnessDay807).where(WellnessDay807.day == day))
        before = snapshot(row, DAY_FIELDS) if row else None
        # Retain ratings for disabled metrics; blanks clear enabled metrics only.
        values = json.loads(row.values_json) if row else {}
        for key in order:
            values.pop(key, None)
        values.update(metric_values(form, order))
        notes = checked_notes(form.get("notes"))
        if not values and not notes:
            raise ValueError("Enter a rating or note, or use Delete check-in.")
        if row is None:
            row = WellnessDay807(day=day)
            db.add(row)
        row.values_json = json.dumps(values, sort_keys=True)
        row.notes = notes
        db.flush()
        record(db, "wellness_day807", row.id, "edit" if before else "create", before, snapshot(row, DAY_FIELDS))
        db.commit()
    except ValueError as exc:
        db.rollback()
        _bad(exc)
    return _today(day)

@router.post("/wellness807/days/{rid}/delete")
def delete_wellness807(rid: int, db: Session = Depends(get_scoped_db390)):
    require_inventory_write(db)
    row = db.get(WellnessDay807, rid)
    if not row:
        raise HTTPException(404, "Check-in not found.")
    day = row.day
    record(db, "wellness_day807", rid, "delete", snapshot(row, DAY_FIELDS))
    db.delete(row)
    db.commit()
    return _today(day)

@router.post("/wellness807/preferences")
async def preferences807(request: Request, db: Session = Depends(get_scoped_db390)):
    form = await request.form()
    try:
        enabled = metric_order(form.getlist("enabled"))
        ranked = sorted(enabled, key=lambda k: (int(form.get("rank_" + k, 99)), list(METRICS).index(k)))
        if any(not 1 <= int(form.get("rank_" + k, 99)) <= len(METRICS) for k in enabled):
            raise ValueError("Metric order is outside the supported range.")
    except (ValueError, TypeError) as exc:
        _bad(exc)
    require_inventory_write(db)
    row = db.get(WellnessPreferences807, 1)
    if row is None:
        row = WellnessPreferences807(id=1)
        db.add(row)
    row.metrics_json = json.dumps(ranked)
    db.commit()
    return _today()

@router.post("/wellness807/symptoms/save")
async def save_symptom807(request: Request, db: Session = Depends(get_scoped_db390)):
    form = await request.form()
    try:
        values = episode_values(form, SYMPTOMS)
        rid = int(form.get("record_id") or 0)
    except (ValueError, TypeError) as exc:
        _bad(exc)
    require_inventory_write(db)
    row = db.get(Symptom807, rid) if rid else Symptom807()
    if row is None:
        raise HTTPException(404, "Symptom not found.")
    fields = ("symptom", *EPISODE_FIELDS)
    before = snapshot(row, fields) if rid else None
    row.symptom = str(form.get("kind"))
    for key, value in values.items():
        setattr(row, key, value)
    if not rid:
        db.add(row)
    db.flush()
    record(db, "symptom807", row.id, "edit" if rid else "create", before, snapshot(row, fields))
    db.commit()
    return _today(anchor="symptoms807")

@router.post("/wellness807/symptoms/{rid}/delete")
def delete_symptom807(rid: int, db: Session = Depends(get_scoped_db390)):
    require_inventory_write(db)
    row = db.get(Symptom807, rid)
    if row is None:
        raise HTTPException(404, "Symptom not found.")
    record(db, "symptom807", row.id, "delete", snapshot(row, ("symptom", *EPISODE_FIELDS)))
    db.delete(row)
    db.commit()
    return _today(anchor="symptoms807")

def reaction_parent807(db, source, did):
    model = {"dose": DoseLog, "blend": BlendDose}.get(source)
    if model is None:
        raise HTTPException(404)
    parent = db.get(model, did)
    if parent is None or parent.kind != "dose":
        raise HTTPException(404, "Administration not found.")
    column = SiteReaction807.dose_id if source == "dose" else SiteReaction807.blend_dose_id
    return parent, column

def reaction_context807(db, source, did):
    column = SiteReaction807.dose_id if source == "dose" else SiteReaction807.blend_dose_id
    return dict(reaction807_source=source, reaction807_types=REACTIONS,
                reaction807_rows=list(db.scalars(select(SiteReaction807).where(column == did)
                                              .order_by(SiteReaction807.onset_at.desc()))),
                reaction807_now=datetime.now().strftime("%Y-%m-%dT%H:%M"))

def _reaction_back(source, did):
    path = f"/doses/{did}/edit" if source == "dose" else f"/doses/blends/{did}/edit"
    return RedirectResponse(path + "#site-reactions807", status_code=303)

@router.post("/wellness807/reactions/{source}/{did}/save")
async def save_reaction807(source: str, did: int, request: Request, db: Session = Depends(get_scoped_db390)):
    form = await request.form()
    try:
        values = episode_values(form, REACTIONS, allow_absent=True)
        rid = int(form.get("record_id") or 0)
    except (TypeError, ValueError) as exc:
        _bad(exc)
    require_inventory_write(db)
    parent, column = reaction_parent807(db, source, did)
    if values["onset_at"] < parent.taken_at:
        raise HTTPException(422, "Reaction onset cannot precede the administration.")
    row = db.scalar(select(SiteReaction807).where(SiteReaction807.id == rid, column == did)) if rid else SiteReaction807()
    if row is None:
        raise HTTPException(404, "Reaction not found.")
    kind = str(form.get("kind"))
    others = list(db.scalars(select(SiteReaction807).where(column == did, SiteReaction807.id != rid)))
    if any((r.reaction == "No reaction reported") != (kind == "No reaction reported") for r in others):
        raise HTTPException(422, "Remove the conflicting reaction report before saving.")
    if kind == "No reaction reported" and others:
        raise HTTPException(422, "Absence of reaction is already recorded.")
    before = snapshot(row, REACTION_FIELDS) if rid else None
    row.dose_id = did if source == "dose" else None
    row.blend_dose_id = did if source == "blend" else None
    row.site = parent.site or ""
    row.reaction = kind
    for key, value in values.items():
        setattr(row, key, value)
    if not rid:
        db.add(row)
    db.flush()
    record(db, "site_reaction807", row.id, "edit" if rid else "create", before, snapshot(row, REACTION_FIELDS))
    db.commit()
    return _reaction_back(source, did)

@router.post("/wellness807/reactions/{source}/{did}/{rid}/delete")
def delete_reaction807(source: str, did: int, rid: int, db: Session = Depends(get_scoped_db390)):
    require_inventory_write(db)
    parent, column = reaction_parent807(db, source, did)
    row = db.scalar(select(SiteReaction807).where(SiteReaction807.id == rid, column == did))
    if row is None:
        raise HTTPException(404, "Reaction not found.")
    record(db, "site_reaction807", row.id, "delete", snapshot(row, REACTION_FIELDS))
    db.delete(row)
    db.commit()
    return _reaction_back(source, did)

# Rotation settings use explicit recording preferences, never anatomical suitability.
from ..anatomical_sites807 import SITES, SITE_BY_CODE
from ..site_history807 import ROUTES, rotation_key807, site_snapshot807, history807
from ..wellness_models807 import RotationPreference807, SiteExclusion807
from ..models import Compound, Blend, Protocol, Vial, ProtocolItem
from ..wellness807 import checked_time

def rotation_context807(db):
    return dict(rotation807_sites=SITES, rotation807_routes=ROUTES,
                rotation807_rows=list(db.scalars(select(RotationPreference807).order_by(RotationPreference807.key))),
                rotation807_exclusions=list(db.scalars(select(SiteExclusion807).order_by(SiteExclusion807.until_at.desc()))),
                rotation807_compounds=list(db.scalars(select(Compound).order_by(Compound.name))),
                rotation807_blends=list(db.scalars(select(Blend).order_by(Blend.label))),
                rotation807_protocols=list(db.scalars(select(Protocol).order_by(Protocol.name))))

def _rotation_back():
    return RedirectResponse("/protocols#rotation807", status_code=303)

@router.post("/wellness807/rotation/save")
async def save_rotation807(request: Request, db: Session = Depends(get_scoped_db390)):
    form = await request.form()
    require_inventory_write(db)
    try:
        raw = str(form.get("scope", "global:0")).split(":")
        if len(raw) != 2:
            raise ValueError("Invalid rotation scope.")
        scope, ident = raw[0], int(raw[1])
        identity = None if scope == "global" and ident == 0 else ident
        route = str(form.get("route", ""))
        key = rotation_key807(scope, identity, route)
        model = {"compound": Compound, "blend": Blend, "protocol": Protocol}.get(scope)
        if model and db.get(model, identity) is None:
            raise ValueError("Rotation source not found.")
        sequence = tuple(x.strip() for x in str(form.get("sequence", "")).split(",") if x.strip())
        if len(set(sequence)) != len(sequence) or any(x not in SITE_BY_CODE for x in sequence):
            raise ValueError("Use distinct canonical recording locations.")
        minimum, recent = int(form.get("minimum_hours", 0)), int(form.get("recent_hours", 72))
        if not (0 <= minimum <= 8760 and 0 <= recent <= 8760):
            raise ValueError("Intervals must be between 0 and 8760 hours.")
    except (ValueError, TypeError) as exc:
        db.rollback()
        _bad(exc)
    row = db.get(RotationPreference807, key)
    if row is None:
        row = RotationPreference807(key=key, route=route)
        db.add(row)
    row.sequence_json, row.minimum_hours, row.recent_hours = json.dumps(sequence), minimum, recent
    db.commit()
    return _rotation_back()

@router.post("/wellness807/rotation/delete")
async def delete_rotation807(request: Request, db: Session = Depends(get_scoped_db390)):
    form = await request.form()
    require_inventory_write(db)
    row = db.get(RotationPreference807, str(form.get("key", "")))
    if row is None:
        raise HTTPException(404, "Rotation not found.")
    db.delete(row)
    db.commit()
    return _rotation_back()

@router.post("/wellness807/exclusions/save")
async def save_exclusion807(request: Request, db: Session = Depends(get_scoped_db390)):
    form = await request.form()
    require_inventory_write(db)
    try:
        site = str(form.get("site", ""))
        if site not in SITE_BY_CODE:
            raise ValueError("Choose a canonical recording location.")
        now = datetime.now()
        until = checked_time(form.get("until_at"), now=now+timedelta(days=365))
        if until <= now:
            raise ValueError("Exclusion must end in the future.")
        notes = checked_notes(form.get("notes"))
    except ValueError as exc:
        db.rollback()
        _bad(exc)
    row = db.get(SiteExclusion807, site)
    if row is None:
        row = SiteExclusion807(site=site)
        db.add(row)
    row.until_at, row.notes = until, notes
    db.commit()
    return _rotation_back()

@router.post("/wellness807/exclusions/{site}/delete")
def delete_exclusion807(site: str, db: Session = Depends(get_scoped_db390)):
    require_inventory_write(db)
    row = db.get(SiteExclusion807, site)
    if row is None:
        raise HTTPException(404, "Exclusion not found.")
    db.delete(row)
    db.commit()
    return _rotation_back()

@router.get("/wellness807/site-summary")
def site_summary807(source: str = "", route: str = "", protocol_item: int | None = None,
                    db: Session = Depends(get_scoped_db390)):
    if route not in ROUTES:
        raise HTTPException(422, "Unknown route.")
    compound = blend = protocol = None
    if source:
        from ..blend_dose_unified710 import source_identity710
        try:
            kind, ident = source_identity710(source)
        except ValueError:
            raise HTTPException(422, "Unknown source.") from None
        if kind == "blend":
            if db.get(Blend, ident) is None:
                raise HTTPException(404)
            blend = ident
        else:
            vial = db.get(Vial, ident)
            if vial is None:
                raise HTTPException(404)
            compound = vial.compound_id
    if protocol_item is not None:
        item = db.get(ProtocolItem, protocol_item)
        if item is None:
            raise HTTPException(404)
        protocol = item.protocol_id
        compound = item.compound_id
    return site_snapshot807(db, datetime.now(), compound=compound, blend=blend, protocol=protocol, route=route)
