#!/usr/bin/env python3
"""Release 664: exact-SHA, no-schema read-only Workout Calendar source review."""
from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

BASE664 = "20b9c0599ebf9ff4ea05ccddcd7130beaf6027a1"

# The four existing files are pinned to exact reviewed Git blobs. All other
# paths are new; a source mutation, migration, or unrelated change fails closed.
REVIEWED664 = {
    "app/main.py": (
        "7c02505501a750bdf0fedca709a0d745555e3a6f",
        "65db9d2fd3c96f7538e31ecf7b784d397ffc0822",
    ),
    "app/templates/workouts654.html": (
        "ce14357b93389a4ceb06587ec011f927dd3196eb",
        "43c21acd38124a59c02a34769e6461068b2d664e",
    ),
    "app/templates/_workout_dashboard661.html": (
        "ffac45f3dcaf3306a78756d7d1e21ff9b923b941",
        "72019f4e3ef7111b30fdcb9bf2383f960d62c6c4",
    ),
    "app/templates/workout_review663.html": (
        "c5d2917eca7db1ff24869d062160f58dd29c9c23",
        "5ec088575d9210845175f6a12c049a9870f068e6",
    ),
}
NEW664 = frozenset({
    "app/routers/workouts664.py",
    "app/templates/workout_calendar664.html",
    "app/static/css/tracker-workout-calendar664.css",
    "tests/test_workouts664.py",
    "tests/browser/test_workout_calendar664.py",
    "scripts/tracker-workout-dev664.sh",
    "scripts/tracker-workout-review664.py",
    "scripts/tracker-release-scoped664.sh",
    "docs/release-664-workout-calendar.md",
})
REQUIRED664 = frozenset(REVIEWED664) | NEW664


def git(root: Path, *args: str) -> str:
    proc = subprocess.run(
        ["git", "-c", f"safe.directory={root}", "-C", str(root), *args],
        capture_output=True, text=True, check=False,
    )
    if proc.returncode:
        raise ValueError("Source review failed: " + proc.stderr[:180])
    return proc.stdout.strip()


def validate(root: Path, base: str, target: str) -> None:
    if base != BASE664 or git(root, "rev-parse", "HEAD") != target:
        raise ValueError("Unexpected DEV baseline or candidate SHA")
    git(root, "merge-base", "--is-ancestor", base, target)
    changed = set(git(root, "diff", "--name-only", base, target).splitlines())
    if changed != REQUIRED664:
        raise ValueError("Unreviewed or missing Release 664 paths: " +
                         repr(sorted(changed ^ REQUIRED664)))

    for path, (expected_before, expected_after) in REVIEWED664.items():
        old = git(root, "rev-parse", f"{base}:{path}")
        new = git(root, "rev-parse", f"{target}:{path}")
        if (old, new) != (expected_before, expected_after):
            raise ValueError("Unexpected existing source mutation: " + path)

    main = (root / "app/main.py").read_text(encoding="utf-8")
    for token in ("from .routers import workouts664",
                  "app.include_router(workouts664.router)"):
        if main.count(token) != 1:
            raise ValueError("Workout Calendar registration missing or duplicated")

    route = (root / "app/routers/workouts664.py").read_text(encoding="utf-8")
    for token in (
        'get_scoped_db390',
        '@router.get("/workouts/calendar")',
        "MONTH664.fullmatch(value)",
        "MIN_YEAR664 = 1900",
        "MAX_YEAR664 = 2100",
        "WorkoutSession654.completed_at.is_not(None)",
        "WorkoutSet654.session_id == WorkoutSession654.id",
        "WorkoutSession654.started_at >= start",
        "WorkoutSession654.started_at < upper",
        "upper = min(end, tomorrow)",
        "func.count(WorkoutSet654.id)",
        "CALENDAR664.monthdatescalendar(first.year, first.month)",
        "by_date[row.started_at.date()].append(row)",
        "get_scoped_db390",
    ):
        if token not in route:
            raise ValueError("Missing scoped completed-session constraint: " + token)
    for forbidden in (
        "@router.post(", "@router.put(", "@router.delete(",
        "db.add(", "db.delete(", "db.commit(", "Base.metadata",
        "ALTER TABLE", "DROP TABLE", "engine.begin", "SessionLocal",
        "get_db(", "httpx", "requests.", "urlopen(", "eval(", "exec(",
    ):
        if forbidden in route:
            raise ValueError("Unreviewed write/network/schema logic: " + forbidden)
    if route.count("@router.get(") != 1:
        raise ValueError("Only one read-only calendar GET may be registered")

    page = (root / "app/templates/workout_calendar664.html").read_text(
        encoding="utf-8"
    )
    for required in (
        'workout_calendar.sessions', 'workout_calendar.training_days',
        'workout_calendar.sets', 'workout_calendar.weeks',
        'workout_calendar.days', 'data-date664=',
        'scope="col"', 'aria-current="date"',
        'href="#workout664-day-{{ cell.day.isoformat() }}"',
        'id="workout664-day-{{ group.day.isoformat() }}"',
        'href="/workouts/sessions/{{ item.session_id }}/review"',
        '/workouts/calendar?month={{ workout_calendar.previous }}',
        '/workouts/calendar?month={{ workout_calendar.next }}',
    ):
        if required not in page:
            raise ValueError("Missing accessible calendar or review link: " + required)
    for forbidden in ("<form", "fetch(", "<script", "method=\"post\""):
        if forbidden in page:
            raise ValueError("Calendar must be a read-only page")

    for path in (
        "app/templates/workouts654.html",
        "app/templates/_workout_dashboard661.html",
    ):
        if 'href="/workouts/calendar"' not in (root / path).read_text(
            encoding="utf-8"
        ):
            raise ValueError("Workout Calendar entry point missing: " + path)
    review = (root / "app/templates/workout_review663.html").read_text(
        encoding="utf-8"
    )
    if '/workouts/calendar?month={{ workout.started_at.strftime(' not in review:
        raise ValueError("Session review calendar deep link missing")
    css = (root / "app/static/css/tracker-workout-calendar664.css").read_text(
        encoding="utf-8"
    )
    if "overflow-x:auto" not in css or "workout664-grid" not in css:
        raise ValueError("Phone calendar layout bounds missing")
    print("WORKOUT_664_EXACT_SCOPED_SOURCE_REVIEW=PASSED")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--base", required=True)
    parser.add_argument("--target", required=True)
    args = parser.parse_args()
    validate(args.root.resolve(), args.base, args.target)
