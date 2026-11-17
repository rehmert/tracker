"""Release 656: read-only progress reporting on existing Workout set records.

No schema migration, no writes, no estimates of one-rep maximum. Trends show
the heaviest load actually logged during each of the most recent 16 sessions.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from urllib.parse import quote
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import services
from ..scoped_db390 import get_scoped_db390
from ..templating import render
from ..workout_models654 import WorkoutEquipment654, WorkoutSession654, WorkoutSet654
from ..workout_models668 import WorkoutLoadSemantics668

router = APIRouter()

MAX_RECENT_SETS656 = 30
MAX_TREND_SESSIONS656 = 16


def trend_points656(values: list[float]) -> str:
    """Pure, bounded SVG coordinates, not derived from untrusted markup."""
    if len(values) < 2:
        return ""
    low, high = min(values), max(values)
    span = high - low
    coords = []
    for index, weight in enumerate(values):
        x = 28 + index * 644 / (len(values) - 1)
        y = 138 - 98 * ((weight - low) / span if span else 0.5)
        coords.append(f"{x:.1f},{y:.1f}")
    return " ".join(coords)




@router.get("/workouts/qr/scan")
def scan_lookup656(code: str = "", db: Session = Depends(get_scoped_db390)):
    """Internal only: unknown scanned codes prefill a new machine mapping."""
    code = code.strip()
    if not code or len(code) > 1024:
        return services.flash_redirect("/workouts", err="QR code must contain 1–1024 characters.")
    machine = db.scalar(
        select(WorkoutEquipment654)
        .where(WorkoutEquipment654.qr_value == code)
        .limit(1)
    )
    if machine is not None:
        return services.flash_redirect(
            f"/workouts?machine={machine.id}", msg=f"Matched {machine.name}."
        )
    # Decode only into an editable local form; never navigate to the QR URL.
    return services.flash_redirect(
        "/workouts?unmapped_qr=" + quote(code, safe=""),
        err="Unknown machine QR. Add equipment below to save this mapping.",
    )

@router.get("/workouts/equipment/{equipment_id}/progress")
def progress656(
    equipment_id: int, request: Request, db: Session = Depends(get_scoped_db390),
):
    machine = db.get(WorkoutEquipment654, equipment_id)
    if machine is None:
        raise HTTPException(status_code=404, detail="Equipment not found")
    source = WorkoutSet654

    total_sets = db.scalar(
        select(func.count(source.id)).where(source.equipment_id == equipment_id)
    ) or 0
    latest_sets = list(db.scalars(
        select(source)
        .where(source.equipment_id == equipment_id)
        .order_by(source.performed_at.desc(), source.id.desc())
        .limit(MAX_RECENT_SETS656)
    ))
    best = db.scalar(
        select(source)
        .where(source.equipment_id == equipment_id)
        .order_by(
            source.weight_lb.desc(), source.reps.desc(),
            source.performed_at.desc(), source.id.desc(),
        )
        .limit(1)
    )
    trend_rows = list(db.execute(
        select(
            WorkoutSession654.id.label("session_id"),
            WorkoutSession654.started_at.label("started_at"),
            func.max(source.weight_lb).label("best_lb"),
            func.count(source.id).label("sets"),
        )
        .join(WorkoutSession654, source.session_id == WorkoutSession654.id)
        .where(source.equipment_id == equipment_id)
        .group_by(WorkoutSession654.id)
        .order_by(
            WorkoutSession654.started_at.desc(),
            WorkoutSession654.id.desc(),
        )
        .limit(MAX_TREND_SESSIONS656)
    ))
    trend = list(reversed(trend_rows))
    points = trend_points656([float(entry.best_lb) for entry in trend])
    lows = [float(entry.best_lb) for entry in trend]

    return render(
        request, "workout_progress656.html",
        machine=machine, total_sets=total_sets,
        load_semantics668=db.get(WorkoutLoadSemantics668, equipment_id),
        latest=latest_sets[0] if latest_sets else None,
        best=best, recent=latest_sets, trend=trend,
        points=points, chart_min=min(lows) if lows else 0.0,
        chart_max=max(lows) if lows else 0.0,
        total_sessions=len(trend),
        trend_limit=MAX_TREND_SESSIONS656,
        sets_limit=MAX_RECENT_SETS656,
    )
