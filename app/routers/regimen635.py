"""Release 635: supplement/medication catalog, schedules and recorded intake.

No dosing recommendations, implicit food-nutrient additions or vial mutations.
"""
from datetime import date, datetime, timedelta
import json
import re

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..inventory_lock import reserve_inventory_write
from ..models import ChangeAudit, RegimenItem, RegimenSchedule, RegimenEntry, RegimenProductFacts639
from ..scoped_db390 import get_scoped_db390
from ..templating import render
from .. import services

router = APIRouter()
KINDS = ("supplement", "medication")
CADENCES = ("daily", "weekly", "interval", "prn")
MEALS = ("", "breakfast", "lunch", "dinner", "snack", "other")
OUTCOMES = ("taken", "skipped")


def _day(raw, default=None):
    if not raw:
        if default is not None:
            return default
        raise ValueError("Date is required.")
    try:
        parsed = date.fromisoformat(str(raw))
    except ValueError:
        raise ValueError("Enter a valid date.") from None
    if not 2000 <= parsed.year <= 2100:
        raise ValueError("Date is outside the supported range.")
    return parsed


def _text(form, key, limit, required=False):
    value = str(form.get(key, "")).strip()
    if len(value) > limit or (required and not value):
        raise ValueError(f"{key.replace('_', ' ').capitalize()} must contain 1–{limit} characters." if required else f"{key} is too long.")
    return value


def _choice(form, key, allowed):
    value = str(form.get(key, "")).strip()
    if value not in allowed:
        raise ValueError(f"Choose a valid {key}.")
    return value


def _time(raw):
    value = str(raw or "").strip()
    if value and (not re.fullmatch(r"(?:[01][0-9]|2[0-3]):[0-5][0-9]", value)):
        raise ValueError("Time must use HH:MM.")
    return value


def _audit(db, kind, ident, action, before=None, after=None):
    db.add(ChangeAudit(
        entity_type=kind, entity_id=ident, action=action,
        before_json=json.dumps(before or {}, sort_keys=True),
        after_json=json.dumps(after or {}, sort_keys=True),
    ))


def _item_values(form):
    return dict(
        kind=_choice(form, "kind", KINDS),
        name=_text(form, "name", 160, True),
        ingredient=_text(form, "ingredient", 160),
        strength=_text(form, "strength", 80),
        form=_text(form, "form", 60),
        instructions=_text(form, "instructions", 2000),
        purpose=_text(form, "purpose", 2000),
        prescriber=_text(form, "prescriber", 160),
        notes=_text(form, "notes", 2000),
    )


def _facts_values(form):
    """Validate editable product label facts; never accept an unbounded payload."""
    raw = str(form.get("label_facts_json", "")).strip()
    if not raw:
        return None
    if len(raw) > 120000:
        raise ValueError("Supplement label information exceeds the supported size.")
    try:
        data = json.loads(raw)
    except (ValueError, TypeError):
        raise ValueError("Supplement label information is invalid.") from None
    if not isinstance(data, dict):
        raise ValueError("Supplement label information must be an object.")
    text_limits = {
        "brand": 160, "source": 32, "source_id": 100,
        "serving_quantity": 40, "serving_unit": 80,
        "other_ingredients": 4000, "servings_per_container": 80,
        "upc_sku": 80,
    }
    values = {}
    for key, limit in text_limits.items():
        value = data.get(key, "")
        if not isinstance(value, str) or len(value) > limit:
            raise ValueError("Invalid supplement label field: " + key)
        values[key] = value.strip()
    rows = data.get("ingredients", [])
    if not isinstance(rows, list) or len(rows) > 300:
        raise ValueError("Supplement ingredient list is invalid or too large.")
    normalized = []
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("Invalid supplement ingredient row.")
        values_row = {}
        for key, limit in (("name", 160), ("amount", 40), ("unit", 40),
                           ("basis", 100), ("daily_value", 160)):
            value = row.get(key, "")
            if not isinstance(value, str) or len(value) > limit:
                raise ValueError("Invalid ingredient " + key)
            values_row[key] = value.strip()
        if values_row["name"]:
            normalized.append(values_row)
    values["ingredients_json"] = json.dumps(normalized, ensure_ascii=False)
    return values


def _store_facts(db, item_id, values):
    if values is None:
        return
    existing = db.scalar(select(RegimenProductFacts639).where(
        RegimenProductFacts639.item_id == item_id))
    if existing is None:
        existing = RegimenProductFacts639(item_id=item_id)
        db.add(existing)
    for key, value in values.items():
        setattr(existing, key, value)
    if values["source"] and values["source_id"]:
        existing.imported_at = datetime.utcnow()


def _schedule_values(form):
    cadence = _choice(form, "cadence", CADENCES)
    start = _day(form.get("start_on"), date.today())
    end = _day(form.get("end_on")) if form.get("end_on") else None
    if end and end < start:
        raise ValueError("End date cannot precede start date.")
    weekdays = ""
    interval_days = None
    if cadence == "weekly":
        raw = str(form.get("weekdays", "")).strip()
        days = raw.split(",") if raw else []
        if not days or len(days) > 7 or any(x not in "0123456" or len(x) != 1 for x in days):
            raise ValueError("Enter weekdays as comma-separated numbers 0–6 (Monday–Sunday).")
        weekdays = ",".join(str(x) for x in sorted({int(x) for x in days}))
    if cadence == "interval":
        raw = str(form.get("interval_days", "")).strip()
        if not raw.isdecimal() or not 1 <= int(raw) <= 365:
            raise ValueError("Interval must be 1–365 days.")
        interval_days = int(raw)
    return dict(
        cadence=cadence, weekdays=weekdays, interval_days=interval_days,
        start_on=start, end_on=end,
        at_time=_time(form.get("at_time")),
        amount=_text(form, "amount", 80, True),
        meal=_choice(form, "meal", MEALS),
    )


def due_on(schedule, day):
    """Pure calendar evaluation; no reminder or administration side effects."""
    if not schedule.active or day < schedule.start_on or (schedule.end_on and day > schedule.end_on):
        return False
    if schedule.cadence == "prn":
        return False
    if schedule.cadence == "daily":
        return True
    if schedule.cadence == "weekly":
        return str(day.weekday()) in schedule.weekdays.split(",")
    if schedule.cadence == "interval":
        return bool(schedule.interval_days) and (day - schedule.start_on).days % schedule.interval_days == 0
    return False


def _get(db, kind, ident):
    cls = {"item": RegimenItem, "schedule": RegimenSchedule, "entry": RegimenEntry}[kind]
    obj = db.get(cls, ident)
    if obj is None:
        raise HTTPException(404, "Regimen record not found")
    return obj


def _redirect(day=None, msg="", err=""):
    back = "/regimen" + (f"?day={day.isoformat()}" if day else "")
    return services.flash_redirect(back, msg=msg, err=err)


@router.get("/regimen")
def regimen_page(request: Request, day: str = "", db: Session = Depends(get_scoped_db390)):
    try:
        selected = _day(day, date.today())
    except ValueError:
        selected = date.today()
    items = list(db.scalars(select(RegimenItem).order_by(RegimenItem.kind, RegimenItem.name, RegimenItem.id)))
    product_facts = {
        facts.item_id: json.dumps({
            "brand": facts.brand,
            "source": facts.source,
            "source_id": facts.source_id,
            "serving_quantity": facts.serving_quantity,
            "serving_unit": facts.serving_unit,
            "other_ingredients": facts.other_ingredients,
            "servings_per_container": facts.servings_per_container,
            "upc_sku": facts.upc_sku,
            "ingredients": json.loads(facts.ingredients_json or "[]"),
        }, ensure_ascii=False)
        for facts in db.scalars(select(RegimenProductFacts639))
    }
    schedules = list(db.scalars(select(RegimenSchedule).order_by(RegimenSchedule.id.desc())))
    start = datetime.combine(selected, datetime.min.time())
    end = start + timedelta(days=1)
    entries = list(db.scalars(select(RegimenEntry).where(
        RegimenEntry.logged_at >= start, RegimenEntry.logged_at < end
    ).order_by(RegimenEntry.logged_at.desc(), RegimenEntry.id.desc())))
    due = [s for s in schedules if s.item.active and due_on(s, selected)]
    recorded = {e.schedule_id for e in entries if e.schedule_id is not None}
    history = list(db.scalars(select(RegimenEntry).order_by(
        RegimenEntry.logged_at.desc(), RegimenEntry.id.desc()
    ).limit(50)))
    return render(
        request, "regimen635.html", items=items, schedules=schedules,
        product_facts=product_facts,
        due=due, recorded=recorded, entries=entries, history=history,
        day=selected, prev_day=selected - timedelta(days=1),
        next_day=selected + timedelta(days=1), today=date.today(),
        kinds=KINDS, meals=MEALS,
    )


@router.post("/regimen/items")
async def create_item(request: Request, db: Session = Depends(get_scoped_db390)):
    form = await request.form()
    try:
        values = _item_values(form)
        facts = _facts_values(form)
    except ValueError as exc:
        return _redirect(err=str(exc))
    if not reserve_inventory_write(db):
        return _redirect(err="Database is busy.")
    item = RegimenItem(**values)
    db.add(item)
    db.flush()
    _store_facts(db, item.id, facts)
    _audit(db, "regimen_item", item.id, "create", after=values)
    db.commit()
    return _redirect(msg="Catalog item added.")


@router.post("/regimen/items/{item_id}/edit")
async def edit_item(item_id: int, request: Request, db: Session = Depends(get_scoped_db390)):
    form = await request.form()
    try:
        values = _item_values(form)
    except ValueError as exc:
        return _redirect(err=str(exc))
    if not reserve_inventory_write(db):
        return _redirect(err="Database is busy.")
    item = _get(db, "item", item_id)
    before = {key: getattr(item, key) for key in values}
    before["active"] = item.active
    for key, value in values.items():
        setattr(item, key, value)
    _store_facts(db, item.id, facts)
    item.active = str(form.get("active", "")) == "yes"
    after = {key: getattr(item, key) for key in values}
    after["active"] = item.active
    if before != after:
        _audit(db, "regimen_item", item.id, "edit", before, after)
    db.commit()
    return _redirect(msg="Catalog item updated.")


@router.post("/regimen/items/{item_id}/archive")
def archive_item(item_id: int, db: Session = Depends(get_scoped_db390)):
    if not reserve_inventory_write(db):
        return _redirect(err="Database is busy.")
    item = _get(db, "item", item_id)
    before = {"active": item.active}
    item.active = False
    if before["active"]:
        _audit(db, "regimen_item", item.id, "archive", before, {"active": False})
    db.commit()
    return _redirect(msg="Item archived; history retained.")


@router.post("/regimen/schedules")
async def create_schedule(request: Request, db: Session = Depends(get_scoped_db390)):
    form = await request.form()
    try:
        item_id = int(str(form.get("item_id", "")))
        values = _schedule_values(form)
    except (ValueError, TypeError) as exc:
        return _redirect(err=str(exc))
    if not reserve_inventory_write(db):
        return _redirect(err="Database is busy.")
    item = _get(db, "item", item_id)
    if not item.active:
        db.rollback()
        return _redirect(err="Cannot schedule an archived item.")
    schedule = RegimenSchedule(item_id=item_id, **values)
    db.add(schedule)
    db.flush()
    _audit(db, "regimen_schedule", schedule.id, "create", after=dict(
        item_id=item_id, cadence=values["cadence"], amount=values["amount"]
    ))
    db.commit()
    return _redirect(msg="Schedule created.")


@router.post("/regimen/schedules/{schedule_id}/edit")
async def edit_schedule(schedule_id: int, request: Request, db: Session = Depends(get_scoped_db390)):
    form = await request.form()
    try:
        values = _schedule_values(form)
    except ValueError as exc:
        return _redirect(err=str(exc))
    if not reserve_inventory_write(db):
        return _redirect(err="Database is busy.")
    schedule = _get(db, "schedule", schedule_id)
    before = {key: getattr(schedule, key) for key in values}
    before["active"] = schedule.active
    for key, value in values.items():
        setattr(schedule, key, value)
    schedule.active = str(form.get("active", "")) == "yes"
    after = {key: getattr(schedule, key) for key in values}
    after["active"] = schedule.active
    def encode(vals):
        return {key: (value.isoformat() if isinstance(value, date) else value)
                for key, value in vals.items()}
    if before != after:
        _audit(db, "regimen_schedule", schedule.id, "edit", encode(before), encode(after))
    db.commit()
    return _redirect(msg="Schedule updated.")


@router.post("/regimen/schedules/{schedule_id}/stop")
def stop_schedule(schedule_id: int, db: Session = Depends(get_scoped_db390)):
    if not reserve_inventory_write(db):
        return _redirect(err="Database is busy.")
    schedule = _get(db, "schedule", schedule_id)
    was = schedule.active
    schedule.active = False
    if was:
        _audit(db, "regimen_schedule", schedule.id, "stop",
               {"active": True}, {"active": False})
    db.commit()
    return _redirect(msg="Schedule stopped; historical entries retained.")


def _entry_values(form, db):
    try:
        item_id = int(str(form.get("item_id", "")))
    except (TypeError, ValueError):
        raise ValueError("Select an item.") from None
    item = _get(db, "item", item_id)
    schedule_id = str(form.get("schedule_id", "")).strip()
    schedule = None
    if schedule_id:
        try:
            schedule = _get(db, "schedule", int(schedule_id))
        except (TypeError, ValueError):
            raise ValueError("Invalid schedule.") from None
        if schedule.item_id != item_id:
            raise ValueError("Schedule does not belong to this item.")
    raw = str(form.get("logged_at", "")).strip()
    try:
        moment = datetime.fromisoformat(raw)
        if moment.tzinfo is not None or not 2000 <= moment.year <= 2100:
            raise ValueError
    except ValueError:
        raise ValueError("Enter a valid local date and time.") from None
    outcome = _choice(form, "outcome", OUTCOMES)
    amount = _text(form, "amount", 80)
    if outcome == "taken" and not amount:
        amount = schedule.amount if schedule else ""
    if outcome == "taken" and not amount:
        raise ValueError("Enter the actual amount taken.")
    return dict(
        item_id=item.id, schedule_id=schedule.id if schedule else None,
        logged_at=moment, outcome=outcome, amount=amount if outcome == "taken" else "",
        meal=_choice(form, "meal", MEALS),
        notes=_text(form, "notes", 2000),
    )


def _entry_snapshot(entry):
    return dict(
        item_id=entry.item_id, schedule_id=entry.schedule_id,
        logged_at=entry.logged_at.isoformat(timespec="minutes"),
        outcome=entry.outcome, amount=entry.amount, meal=entry.meal, notes=entry.notes,
    )


@router.post("/regimen/entries")
async def log_entry(request: Request, db: Session = Depends(get_scoped_db390)):
    form = await request.form()
    try:
        values = _entry_values(form, db)
    except ValueError as exc:
        return _redirect(err=str(exc))
    if not reserve_inventory_write(db):
        return _redirect(err="Database is busy.")
    if values["schedule_id"] is not None:
        day_start = datetime.combine(values["logged_at"].date(), datetime.min.time())
        existing = db.scalar(select(RegimenEntry.id).where(
            RegimenEntry.schedule_id == values["schedule_id"],
            RegimenEntry.logged_at >= day_start,
            RegimenEntry.logged_at < day_start + timedelta(days=1),
        ).limit(1))
        if existing is not None:
            db.rollback()
            return _redirect(values["logged_at"].date(), err="Already logged for this schedule and day. Edit the existing entry instead.")
    entry = RegimenEntry(**values)
    db.add(entry)
    db.flush()
    _audit(db, "regimen_entry", entry.id, "create", after=_entry_snapshot(entry))
    db.commit()
    return _redirect(values["logged_at"].date(), msg="Intake recorded.")


@router.post("/regimen/entries/{entry_id}/edit")
async def edit_entry(entry_id: int, request: Request, db: Session = Depends(get_scoped_db390)):
    form = await request.form()
    try:
        values = _entry_values(form, db)
    except ValueError as exc:
        return _redirect(err=str(exc))
    if not reserve_inventory_write(db):
        return _redirect(err="Database is busy.")
    entry = _get(db, "entry", entry_id)
    before = _entry_snapshot(entry)
    if values["schedule_id"] is not None:
        start = datetime.combine(values["logged_at"].date(), datetime.min.time())
        duplicate = db.scalar(select(RegimenEntry.id).where(
            RegimenEntry.id != entry.id,
            RegimenEntry.schedule_id == values["schedule_id"],
            RegimenEntry.logged_at >= start,
            RegimenEntry.logged_at < start + timedelta(days=1),
        ).limit(1))
        if duplicate is not None:
            db.rollback()
            return _redirect(err="That schedule is already recorded on this date.")
    for key, value in values.items():
        setattr(entry, key, value)
    after = _entry_snapshot(entry)
    if before != after:
        _audit(db, "regimen_entry", entry.id, "edit", before, after)
    db.commit()
    return _redirect(values["logged_at"].date(), msg="Intake corrected.")


@router.post("/regimen/entries/{entry_id}/delete")
def delete_entry(entry_id: int, db: Session = Depends(get_scoped_db390)):
    if not reserve_inventory_write(db):
        return _redirect(err="Database is busy.")
    entry = _get(db, "entry", entry_id)
    before = _entry_snapshot(entry)
    day = entry.logged_at.date()
    _audit(db, "regimen_entry", entry.id, "delete", before=before)
    db.delete(entry)
    db.commit()
    return _redirect(day, msg="Entry deleted; audit preserved.")
