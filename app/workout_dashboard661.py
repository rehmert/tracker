"""Release 661: read-only, user-scoped Workout overview for Tracker home.

Frequency means distinct completed workout sessions with at least one
recorded set. Dates use the recorded workout start (including backfills),
not insertion time. No targets, streaks, recommendations or data writes.
"""
from datetime import date, datetime, time, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .workout_models654 import WorkoutSession654, WorkoutSet654

RECENT_WORKOUT_LIMIT661 = 5
RECENT_DAYS661 = 7
LONG_DAYS661 = 28


def workout_dashboard661(db: Session, today: date) -> dict:
    """Five most recent completed sessions and rolling 7/28 calendar-day counts.

    All operations execute in the caller's authenticated scoped DB session.
    Workouts with no sets and all incomplete sessions are excluded.
    """
    tomorrow = datetime.combine(today + timedelta(days=1), time.min)
    completed = WorkoutSession654.completed_at.is_not(None)
    # Correlated EXISTS prevents extra sets from inflating session counts.
    with_sets = (
        select(WorkoutSet654.id)
        .where(WorkoutSet654.session_id == WorkoutSession654.id)
        .exists()
    )

    def frequency(days: int) -> tuple[int, int]:
        first = datetime.combine(today - timedelta(days=days - 1), time.min)
        row = db.execute(
            select(
                func.count(WorkoutSession654.id).label("sessions"),
                func.count(
                    func.distinct(func.date(WorkoutSession654.started_at))
                ).label("days"),
            )
            .select_from(WorkoutSession654)
            .where(
                completed, with_sets,
                WorkoutSession654.started_at >= first,
                WorkoutSession654.started_at < tomorrow,
            )
        ).one()
        return int(row.sessions), int(row.days)

    sessions7, days7 = frequency(RECENT_DAYS661)
    sessions28, days28 = frequency(LONG_DAYS661)

    recent = list(db.execute(
        select(
            WorkoutSession654.id.label("session_id"),
            WorkoutSession654.started_at.label("started_at"),
            WorkoutSession654.completed_at.label("completed_at"),
            func.count(WorkoutSet654.id).label("sets"),
            func.count(func.distinct(WorkoutSet654.equipment_id)).label("machines"),
        )
        .select_from(WorkoutSession654)
        .join(
            WorkoutSet654, WorkoutSet654.session_id == WorkoutSession654.id,
        )
        .where(
            completed,
            WorkoutSession654.started_at < tomorrow,
        )
        .group_by(
            WorkoutSession654.id,
            WorkoutSession654.started_at,
            WorkoutSession654.completed_at,
        )
        .order_by(
            WorkoutSession654.started_at.desc(),
            WorkoutSession654.id.desc(),
        )
        .limit(RECENT_WORKOUT_LIMIT661)
    ).all())

    in_progress = db.scalar(
        select(WorkoutSession654.id)
        .where(WorkoutSession654.completed_at.is_(None))
        .limit(1)
    ) is not None

    return {
        "sessions7": sessions7,
        "days7": days7,
        "sessions28": sessions28,
        "days28": days28,
        "recent": recent,
        "in_progress": in_progress,
        "limit": RECENT_WORKOUT_LIMIT661,
    }
