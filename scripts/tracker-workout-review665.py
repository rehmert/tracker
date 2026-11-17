#!/usr/bin/env python3
"""Release 665: exact-blob, additive, migration-free Workout planner review."""
from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

BASE665 = "06ffd87697f923808cfa76ea62004304883b9a3d"

REVIEWED665 = {
    "app/main.py": (
        "65db9d2fd3c96f7538e31ecf7b784d397ffc0822",
        "43699dabf223f6ab95d018bcf5fb125800eca3e5",
    ),
    "app/templates/workout_routine_detail655.html": (
        "24fe214d8dbb67ee8533d73a81507697a72a15bc",
        "2410447a25eaea4d4fdade6dd8a0861247621d4a",
    ),
    "app/templates/workout_routines655.html": (
        "3563717d5161eb00256a090b177a9f99a43666e7",
        "7f19df5dc6010ddd15332ac7a50afd01e0ee43c8",
    ),
    "app/templates/workout_quick659.html": (
        "be043ebfc26608acf0b774024e6645f3ce90f033",
        "b5e88539383de165510581233988c4a867102b2a",
    ),
}
NEW665 = frozenset({
    "app/routers/workouts665.py",
    "app/templates/workout_plan665.html",
    "app/static/css/tracker-workout-plan665.css",
    "app/static/js/tracker-workout-plan665.js",
    "tests/test_workouts665.py",
    "tests/browser/test_workout_plan665.py",
    "scripts/tracker-workout-dev665.sh",
    "scripts/tracker-workout-review665.py",
    "scripts/tracker-release-scoped665.sh",
    "docs/release-665-workout-progression.md",
})
REQUIRED665 = frozenset(REVIEWED665) | NEW665


def git(root: Path, *args: str) -> str:
    proc = subprocess.run(
        ["git", "-c", f"safe.directory={root}", "-C", str(root), *args],
        capture_output=True, text=True, check=False,
    )
    if proc.returncode:
        raise ValueError("Source inspection failed: " + proc.stderr[:180])
    return proc.stdout.strip()


def validate(root: Path, base: str, target: str) -> None:
    if base != BASE665 or git(root, "rev-parse", "HEAD") != target:
        raise ValueError("Unexpected DEV baseline or source SHA")
    git(root, "merge-base", "--is-ancestor", base, target)
    changed = set(git(root, "diff", "--name-only", base, target).splitlines())
    if changed != REQUIRED665:
        raise ValueError("Unreviewed or missing Workout 665 paths: " +
                         repr(sorted(changed ^ REQUIRED665)))

    for path, (before, after) in REVIEWED665.items():
        old = git(root, "rev-parse", f"{base}:{path}")
        new = git(root, "rev-parse", f"{target}:{path}")
        if (old, new) != (before, after):
            raise ValueError("Modified existing source differs from review: " + path)

    main = (root / "app/main.py").read_text(encoding="utf-8")
    for needle in ("from .routers import workouts665",
                   "app.include_router(workouts665.router)"):
        if main.count(needle) != 1:
            raise ValueError("New Workout planner registration missing or duplicated")

    route = (root / "app/routers/workouts665.py").read_text(encoding="utf-8")
    for needle in (
        '@router.get("/workouts/routines/{routine_id}/plan")',
        "get_scoped_db390", "db.get(WorkoutRoutine655, routine_id)",
        "WorkoutRoutineItem655.routine_id == routine.id",
        "WorkoutSet654.equipment_id == equipment.id",
        "WorkoutSession654.completed_at.is_not(None)",
        "WorkoutSession654.started_at.desc()",
        "func.count(WorkoutSet654.id)", "func.sum(WorkoutSet654.reps)",
        "func.sum(volume_expr)", "func.max(WorkoutSet654.weight_lb)",
        "MAX_COMPARISON_SESSIONS665 = 2",
    ):
        if needle not in route:
            raise ValueError("Missing scoped completed-set historical guard: " + needle)
    for forbidden in (
        "@router.post(", "@router.put(", "@router.delete(", "db.add(",
        "db.commit(", "db.delete(", "Base.metadata", "SessionLocal",
        "ALTER TABLE", "DROP TABLE", "requests.", "httpx", "urlopen(",
        "get_db(", "exec(", "eval(",
    ):
        if forbidden in route:
            raise ValueError("Unreviewed route write, SQL DDL or external IO: " + forbidden)
    if route.count("@router.get(") != 1:
        raise ValueError("Exactly one new scoped read-only route is expected")

    page = (root / "app/templates/workout_plan665.html").read_text(
        encoding="utf-8"
    )
    for needle in (
        'data-routine-id665="{{ routine.id }}"',
        'data-item-id665="{{ entry.item.id }}"',
        "entry.latest", "entry.previous", "entry.load_change",
        "entry.volume_change", "entry.equipment.name",
        'data-field665="sets"', 'data-field665="reps"',
        'data-field665="weight"',
        'href="/workouts/sessions/{{ entry.latest.session_id }}/review"',
        "only in this browser on this device",
        'id="workout665-clear-all"',
        "tracker-workout-plan665.js?v=665",
    ):
        if needle not in page:
            raise ValueError("Missing planner or actual-history display: " + needle)
    if "<form" in page or "method=\"post\"" in page:
        raise ValueError("Planner must not provide a server write form")

    js = (root / "app/static/js/tracker-workout-plan665.js").read_text(
        encoding="utf-8"
    )
    for needle in (
        "tracker.workout665.plan.routine.", "localStorage.getItem",
        "localStorage.setItem", "localStorage.removeItem",
        "Number.isFinite", "Number.isInteger", "JSON.stringify",
        'data-field665', 'data-item-id665', "addEventListener(\"change\"",
        "Clear", "No workout sets were logged",
    ):
        if needle not in js:
            raise ValueError("Missing local validated draft control: " + needle)
    for forbidden in (
        "fetch(", "XMLHttpRequest", "WebSocket", ".post(", ".submit(",
        "requestSubmit(", "document.cookie", "innerHTML", "eval(", "Function(",
        "http://", "https://",
    ):
        if forbidden in js:
            raise ValueError("Browser-local targets must not write to server")

    for path in (
        "app/templates/workout_routine_detail655.html",
        "app/templates/workout_routines655.html",
        "app/templates/workout_quick659.html",
    ):
        text = (root / path).read_text(encoding="utf-8")
        if 'href="/workouts/routines/{{ routine.id }}/plan"' not in text:
            raise ValueError("Planner entry link missing: " + path)
    css = (root / "app/static/css/tracker-workout-plan665.css").read_text()
    if "@media(max-width:650px)" not in css or "min-width:0" not in css:
        raise ValueError("Mobile planner layout guard missing")

    print("WORKOUT_665_EXACT_READ_ONLY_ROUTINE_PLANNER_SOURCE=PASSED")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--base", required=True)
    parser.add_argument("--target", required=True)
    args = parser.parse_args()
    validate(args.root.resolve(), args.base, args.target)
