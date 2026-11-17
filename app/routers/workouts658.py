"""Release 658: atomic backdated workout entry in the existing scoped SQLite DB.

Only actual user-entered sets are persisted. No edits to completed workouts,
no interference with an active workout, no new tables or schema migrations.
"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta
import math
import re

from fastapi import APIRouter, Depends, Form, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import services
from ..scoped_db390 import get_scoped_db390
from ..templating import render
from ..workout_models654 import WorkoutEquipment654, WorkoutSession654, WorkoutSet654
from ..workout_models655 import WorkoutRoutine655, WorkoutSessionRoutine655
from ..workout_models667 import WorkoutSetType667
from ..workout_csv668 import parse_historical_csv668

router = APIRouter()
MAX_HISTORICAL_SETS658 = 40
MAX_HISTORICAL_HOURS658 = 12
EARLIEST_WORKOUT658 = date(2000, 1, 1)
DAY_PATTERN658 = re.compile(r"\d{4}-\d{2}-\d{2}\Z")
TIME_PATTERN658 = re.compile(r"(?:[01]\d|2[0-3]):[0-5]\d\Z")


def empty_row658() -> dict[str, str]:
    return dict(equipment_id="", weight_lb="", reps="", effort="", set_time="")


def page658(
    request: Request,
    db: Session,
    *,
    values: dict[str, str] | None = None,
    rows: list[dict[str, str]] | None = None,
    error: str = "",
):
    equipment = list(db.scalars(
        select(WorkoutEquipment654).order_by(
            WorkoutEquipment654.gym, WorkoutEquipment654.name, WorkoutEquipment654.id
        )
    ))
    routines = list(db.scalars(
        select(WorkoutRoutine655).order_by(
            WorkoutRoutine655.name, WorkoutRoutine655.id
        )
    ))
    defaults = dict(
        day=datetime.now().date().isoformat(),
        today=datetime.now().date().isoformat(),
        start_time="", end_time="", routine_id="",
    )
    if values is not None:
        defaults.update(values)
    return render(
        request, "workout_backfill658.html",
        equipment=equipment, routines=routines, values=defaults,
        form_rows=rows if rows is not None else [empty_row658() for _ in range(4)],
        error=error, max_rows=MAX_HISTORICAL_SETS658,
    )


def time658(raw: str) -> time:
    if not TIME_PATTERN658.fullmatch(raw):
        raise ValueError("Enter times in HH:MM format.")
    return datetime.strptime(raw, "%H:%M").time()


def window658(day: str, start_time: str, end_time: str) -> tuple[datetime, datetime]:
    if not DAY_PATTERN658.fullmatch(day):
        raise ValueError("Enter a valid workout date.")
    try:
        day_value = date.fromisoformat(day)
    except ValueError as exc:
        raise ValueError("Enter a valid workout date.") from exc
    now = datetime.now()
    if day_value < EARLIEST_WORKOUT658 or day_value > now.date():
        raise ValueError("Workout date must be in the past or today.")
    start = datetime.combine(day_value, time658(start_time))
    end = datetime.combine(day_value, time658(end_time))
    if end <= start:
        raise ValueError("End time must be after start time on the selected date.")
    if end - start > timedelta(hours=MAX_HISTORICAL_HOURS658):
        raise ValueError("A workout may not exceed 12 hours.")
    if end > now:
        raise ValueError("Completed workout cannot end in the future.")
    return start, end


def parse_sets658(
    rows: list[dict[str, str]], start: datetime, end: datetime,
    allowed_ids: set[int],
) -> list[dict]:
    if not 1 <= len(rows) <= MAX_HISTORICAL_SETS658:
        raise ValueError("Enter at most 40 recorded sets.")
    parsed = []
    for index, row in enumerate(rows, 1):
        values = [str(row[key]).strip() for key in (
            "equipment_id", "weight_lb", "reps", "effort", "set_time"
        )]
        if not any(values):
            continue
        machine, weight, reps, effort, logged_time = values
        try:
            machine_id = int(machine)
        except ValueError as exc:
            raise ValueError(f"Set {index}: choose a machine.") from exc
        if machine_id not in allowed_ids:
            raise ValueError(f"Set {index}: choose an existing machine.")
        try:
            pounds = float(weight)
        except ValueError as exc:
            raise ValueError(f"Set {index}: enter a valid weight.") from exc
        if not math.isfinite(pounds) or not 0 <= pounds <= 2000:
            raise ValueError(f"Set {index}: weight must be between 0 and 2,000 lb.")
        try:
            repetitions = int(reps)
        except ValueError as exc:
            raise ValueError(f"Set {index}: repetitions must be a whole number.") from exc
        if not 1 <= repetitions <= 200:
            raise ValueError(f"Set {index}: repetitions must be 1 to 200.")
        value = None
        if effort:
            try:
                value = int(effort)
            except ValueError as exc:
                raise ValueError(f"Set {index}: effort must be 1 to 10.") from exc
            if not 1 <= value <= 10:
                raise ValueError(f"Set {index}: effort must be 1 to 10.")
        # Unknown individual set time is recorded at the entered workout start
        # solely for historical ordering; no current timestamp is fabricated.
        performed_at = datetime.combine(start.date(), time658(logged_time)) if logged_time else start
        if not start <= performed_at <= end:
            raise ValueError(f"Set {index}: set time must be within this workout.")
        parsed.append(dict(
            equipment_id=machine_id, weight_lb=pounds, reps=repetitions,
            effort=value, performed_at=performed_at,
        ))
    if not parsed:
        raise ValueError("Record at least one completed set to save a workout.")
    return parsed


@router.get("/workouts/backfill")
def retroactive_form658(
    request: Request, db: Session = Depends(get_scoped_db390),
):
    return page658(request, db)


@router.post("/workouts/backfill")
def save_retroactive658(
    request: Request,
    day: str = Form(""), start_time: str = Form(""),
    end_time: str = Form(""), routine_id: str = Form(""),
    equipment_id: list[str] = Form([]),
    weight_lb: list[str] = Form([]),
    reps: list[str] = Form([]),
    effort: list[str] = Form([]),
    set_time: list[str] = Form([]),
    db: Session = Depends(get_scoped_db390),
):
    values = dict(
        day=day, start_time=start_time, end_time=end_time, routine_id=routine_id,
    )
    columns = (equipment_id, weight_lb, reps, effort, set_time)
    length = max((len(column) for column in columns), default=0)
    # Reject missing/duplicated columns rather than silently shifting set data.
    if not all(len(column) == length for column in columns):
        return page658(
            request, db, values=values,
            error="Incomplete set rows. Review the form before saving.",
        )
    # Do not render unbounded submitted rows on failure.
    if length > MAX_HISTORICAL_SETS658:
        return page658(
            request, db, values=values,
            error="Maximum 40 sets per historical workout.",
        )
    rows = [
        dict(zip(("equipment_id", "weight_lb", "reps", "effort", "set_time"), fields))
        for fields in zip(*columns)
    ]
    if not rows:
        rows = [empty_row658()]
    try:
        start, end = window658(day, start_time, end_time)
        routine = None
        if routine_id:
            try:
                selected = int(routine_id)
            except ValueError as exc:
                raise ValueError("Choose a saved routine or No routine.") from exc
            routine = db.get(WorkoutRoutine655, selected)
            if routine is None:
                raise ValueError("Selected routine does not exist.")
        allowed_ids = set(db.scalars(select(WorkoutEquipment654.id)))
        prepared = parse_sets658(rows, start, end, allowed_ids)
        # Reject a likely double submission without modifying old sessions.
        duplicate = db.scalar(
            select(WorkoutSession654.id)
            .where(
                WorkoutSession654.started_at == start,
                WorkoutSession654.completed_at == end,
            )
            .limit(1)
        )
        if duplicate is not None:
            raise ValueError("A workout with these exact start/end times already exists.")
    except ValueError as exc:
        return page658(request, db, values=values, rows=rows, error=str(exc))

    # One transaction; any database failure rolls back the session and all sets.
    session = WorkoutSession654(started_at=start, completed_at=end)
    db.add(session)
    db.flush()
    if routine is not None:
        db.add(WorkoutSessionRoutine655(
            session_id=session.id, routine_id=routine.id,
        ))
    for entry in prepared:
        db.add(WorkoutSet654(session_id=session.id, **entry))
    db.commit()
    return services.flash_redirect(
        f"/workouts/sessions/{session.id}", msg="Earlier workout saved."
    )


@router.post("/workouts/backfill/import.csv")
def import_previous_workout_csv668(
    day: str = Form(""), start_time: str = Form(""),
    end_time: str = Form(""), routine_id: str = Form(""),
    csv_text: str = Form(""),
    db: Session = Depends(get_scoped_db390),
):
    """Explicit actual-set CSV import through Release 658 validation."""
    url = "/workouts/backfill"
    try:
        start, end = window658(day, start_time, end_time)
        rows = parse_historical_csv668(csv_text)
        allowed = set(db.scalars(select(WorkoutEquipment654.id)))
        prepared = parse_sets658(rows, start, end, allowed)
        routine = None
        if routine_id:
            if not routine_id.isascii() or not routine_id.isdecimal():
                raise ValueError("Invalid optional routine.")
            routine = db.get(WorkoutRoutine655, int(routine_id))
            if routine is None:
                raise ValueError("Selected routine does not exist.")
        duplicate = db.scalar(select(WorkoutSession654.id)
            .where(
                WorkoutSession654.started_at == start,
                WorkoutSession654.completed_at == end,
            )
            .limit(1))
        if duplicate is not None:
            raise ValueError("A workout with these exact start/end times already exists.")
    except ValueError as exc:
        return services.flash_redirect(url, err=str(exc))
    workout = WorkoutSession654(started_at=start, completed_at=end)
    db.add(workout)
    db.flush()
    if routine is not None:
        db.add(WorkoutSessionRoutine655(
            session_id=workout.id, routine_id=routine.id,
        ))
    for row, original in zip(prepared, rows):
        recorded = WorkoutSet654(session_id=workout.id, **row)
        db.add(recorded)
        if original["set_type"] == "warmup":
            db.flush()
            db.add(WorkoutSetType667(set_id=recorded.id, set_type="warmup"))
    db.commit()
    return services.flash_redirect(
        f"/workouts/sessions/{workout.id}/review",
        msg=f"Imported {len(prepared)} actual historical sets from CSV.",
    )
