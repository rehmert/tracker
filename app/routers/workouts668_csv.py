"""Release 668: scoped CSV workout exports and atomic, idempotent imports.

CSV import never changes existing sessions/sets, does not create unknown
equipment, enforces bounded completed same-day sessions and checks source
records before inserting anything. No remote files or network accesses.
"""
from __future__ import annotations

import csv
from datetime import datetime, timedelta
import hashlib
import io
import math
from collections import defaultdict

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import services
from ..scoped_db390 import get_scoped_db390
from ..templating import render
from ..workout_models654 import WorkoutEquipment654, WorkoutSession654, WorkoutSet654
from ..workout_models667 import WorkoutSetType667
from ..workout_models668 import WorkoutImportReceipt668

router = APIRouter()
CSV_COLUMNS668 = (
    "session_key", "session_started", "session_completed", "equipment_id",
    "weight_lb", "reps", "effort", "set_type", "performed_at",
)
MAX_CSV_BYTES668 = 160000
MAX_CSV_ROWS668 = 500
MAX_CSV_SESSIONS668 = 50


@router.get("/workouts/data")
def data_page668(request: Request, db: Session = Depends(get_scoped_db390)):
    equipment = list(db.scalars(
        select(WorkoutEquipment654).order_by(WorkoutEquipment654.gym, WorkoutEquipment654.name)
    ))
    return render(
        request, "workout_data668.html", equipment=equipment,
        max_rows=MAX_CSV_ROWS668,
    )


@router.get("/workouts/data/export.csv")
def export_workouts668(db: Session = Depends(get_scoped_db390)):
    output = io.StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow(CSV_COLUMNS668)
    rows = db.execute(
        select(WorkoutSet654, WorkoutSession654, WorkoutSetType667.set_type)
        .join(WorkoutSession654, WorkoutSession654.id == WorkoutSet654.session_id)
        .outerjoin(WorkoutSetType667, WorkoutSetType667.set_id == WorkoutSet654.id)
        .where(WorkoutSession654.completed_at.is_not(None))
        .order_by(WorkoutSession654.started_at, WorkoutSession654.id, WorkoutSet654.performed_at, WorkoutSet654.id)
    )
    for entry, workout, kind in rows:
        writer.writerow([
            workout.id, workout.started_at.isoformat(timespec="seconds"),
            workout.completed_at.isoformat(timespec="seconds"),
            entry.equipment_id, entry.weight_lb, entry.reps,
            entry.effort if entry.effort is not None else "",
            kind if kind == "warmup" else "working",
            entry.performed_at.isoformat(timespec="seconds") if entry.performed_at else workout.started_at.isoformat(timespec="seconds"),
        ])
    body = output.getvalue()
    return Response(
        body, media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": 'attachment; filename="tracker-workouts.csv"',
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )


def parse_csv668(raw: str, allowed_ids: set[int], now: datetime):
    if not raw or len(raw.encode("utf-8")) > MAX_CSV_BYTES668 or "\x00" in raw:
        raise ValueError("CSV must contain up to 160 KB of valid text.")
    try:
        reader = csv.DictReader(io.StringIO(raw, newline=""), strict=True)
        if tuple(reader.fieldnames or ()) != CSV_COLUMNS668:
            raise ValueError("CSV header must match Tracker's workout export format.")
        groups = defaultdict(list)
        metadata = {}
        count = 0
        for row in reader:
            count += 1
            if count > MAX_CSV_ROWS668:
                raise ValueError("Maximum 500 CSV set rows per import.")
            if None in row or any(value is None for value in row.values()):
                raise ValueError("CSV rows have inconsistent columns.")
            key = row["session_key"].strip()
            if not key or len(key) > 40 or not key.isascii():
                raise ValueError("Invalid session key.")
            def parse_naive(value: str):
                dt = datetime.fromisoformat(value)
                if dt.tzinfo is not None:
                    raise ValueError("Use local naive timestamps in CSV.")
                return dt
            start = parse_naive(row["session_started"])
            finish = parse_naive(row["session_completed"])
            when = parse_naive(row["performed_at"])
            if (not datetime(2000, 1, 1) <= start <= now or
                    not start < finish <= now or
                    start.date() != finish.date() or
                    finish - start > timedelta(hours=12) or
                    not start <= when <= finish):
                raise ValueError("Invalid workout date, duration or set timestamp.")
            if key in metadata and metadata[key] != (start, finish):
                raise ValueError("Conflicting timestamps for the same session key.")
            metadata[key] = (start, finish)
            machine = int(row["equipment_id"])
            if machine not in allowed_ids:
                raise ValueError("Unknown equipment ID. Map your catalog before importing.")
            weight = float(row["weight_lb"])
            reps_text = row["reps"]
            if not reps_text.isascii() or not reps_text.isdecimal():
                raise ValueError("Repetitions must be whole numbers.")
            reps = int(reps_text)
            effort_raw = row["effort"].strip()
            if effort_raw and (not effort_raw.isascii() or not effort_raw.isdecimal()):
                raise ValueError("Effort must be 1–10 or blank.")
            effort = int(effort_raw) if effort_raw else None
            kind = row["set_type"]
            if (not math.isfinite(weight) or not 0 <= weight <= 2000 or
                    not 1 <= reps <= 200 or
                    (effort is not None and not 1 <= effort <= 10) or
                    kind not in ("warmup", "working")):
                raise ValueError("Weight, repetitions, effort, or set type is invalid.")
            groups[key].append(dict(
                equipment_id=machine, weight_lb=weight, reps=reps,
                effort=effort, performed_at=when, kind=kind,
            ))
        if not count or len(groups) > MAX_CSV_SESSIONS668:
            raise ValueError("Import 1–50 completed workouts at a time.")
        return [(metadata[key], groups[key]) for key in groups]
    except (csv.Error, OverflowError, TypeError) as exc:
        raise ValueError("CSV is malformed or out of range.") from exc


@router.post("/workouts/data/import")
def import_workouts668(
    csv_text: str = Form(""),
    db: Session = Depends(get_scoped_db390),
):
    url = "/workouts/data"
    digest = hashlib.sha256(csv_text.encode("utf-8")).hexdigest()
    if db.get(WorkoutImportReceipt668, digest) is not None:
        return services.flash_redirect(url, err="This exact CSV was previously imported.")
    try:
        allowed = set(db.scalars(select(WorkoutEquipment654.id)))
        sessions = parse_csv668(csv_text, allowed, datetime.now())
        windows = {key for key, _ in sessions}
        if len(windows) != len(sessions):
            raise ValueError("Duplicate workout start/end windows in CSV.")
        # Identical completed windows already present must not be duplicated.
        for start, finish in windows:
            existing = db.scalar(select(WorkoutSession654.id).where(
                WorkoutSession654.started_at == start,
                WorkoutSession654.completed_at == finish,
            ).limit(1))
            if existing is not None:
                raise ValueError("A workout with one of these exact time windows already exists.")
    except (ValueError, TypeError, UnicodeError) as exc:
        return services.flash_redirect(url, err=str(exc))
    for (start, finish), rows in sessions:
        workout = WorkoutSession654(started_at=start, completed_at=finish)
        db.add(workout)
        db.flush()
        for entry in rows:
            kind = entry.pop("kind")
            logged = WorkoutSet654(session_id=workout.id, **entry)
            db.add(logged)
            if kind == "warmup":
                db.flush()
                db.add(WorkoutSetType667(set_id=logged.id, set_type="warmup"))
    db.add(WorkoutImportReceipt668(
        digest=digest, sessions_created=len(sessions),
    ))
    db.commit()
    return services.flash_redirect(
        url, msg=f"Imported {len(sessions)} completed workouts; existing history was not overwritten.",
    )
