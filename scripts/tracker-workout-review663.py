#!/usr/bin/env python3
"""Release 663: exact-SHA source review for Workout Session Review."""
from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

BASE663 = "efd5081a4f68c7f55d46db5e11c88660cfdc1a96"

# Only these four previously deployed paths may change, each to its
# independently reviewed exact Git blob. Every other change is a new file.
REVIEWED663 = {
    "app/main.py": ("2096d41935896c0ea67b0b66048e2bb0b65d7892",
                    "7c02505501a750bdf0fedca709a0d745555e3a6f"),
    "app/templates/workouts654.html":
        ("b7895d8956106a0c7bf671bce70c40eb9a316771",
         "ce14357b93389a4ceb06587ec011f927dd3196eb"),
    "app/templates/workout_quick659.html":
        ("1558264badb86d842fae01c3c12418a6e9176f5e",
         "be043ebfc26608acf0b774024e6645f3ce90f033"),
    "app/templates/workout_history654.html":
        ("98d8e28fcfa3fce1e50410725e7dfaa5c179f82e",
         "39cbcd4c242e7804fc01a14b90a5c20b27df3046"),
}
NEW663 = frozenset({
    "app/routers/workouts663.py",
    "app/templates/workout_review663.html",
    "app/static/css/tracker-workout-review663.css",
    "tests/test_workouts663.py",
    "scripts/tracker-workout-dev663.sh",
    "scripts/tracker-workout-review663.py",
    "scripts/tracker-release-scoped663.sh",
    "docs/release-663-workout-session-review.md",
})
REQUIRED663 = frozenset(REVIEWED663) | NEW663


def git(root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-c", f"safe.directory={root}", "-C", str(root), *args],
        capture_output=True, text=True, check=False,
    )
    if result.returncode:
        raise ValueError("Source inspection failed: " + result.stderr[:180])
    return result.stdout.strip()


def validate(root: Path, base: str, target: str) -> None:
    if base != BASE663 or git(root, "rev-parse", "HEAD") != target:
        raise ValueError("Unexpected DEV qualification baseline or candidate")
    git(root, "merge-base", "--is-ancestor", base, target)
    changed = set(git(root, "diff", "--name-only", base, target).splitlines())
    if changed != REQUIRED663:
        raise ValueError("Unreviewed or missing Release 663 paths: " +
                         repr(sorted(changed ^ REQUIRED663)))

    for path, (expected_before, expected_after) in REVIEWED663.items():
        actual_before = git(root, "rev-parse", f"{base}:{path}")
        actual_after = git(root, "rev-parse", f"{target}:{path}")
        if (actual_before, actual_after) != (expected_before, expected_after):
            raise ValueError("Existing workout source differs from reviewed blob: " + path)

    main = (root / "app/main.py").read_text(encoding="utf-8")
    if ("from .routers import workouts663" not in main or
            "app.include_router(workouts663.router)" not in main):
        raise ValueError("Missing scoped session review router")

    route = (root / "app/routers/workouts663.py").read_text(encoding="utf-8")
    for expected in (
        "get_scoped_db390",
        '@router.get("/workouts/sessions/{session_id}/review")',
        '@router.post("/workouts/finish-review")',
        "db.get(WorkoutSession654, session_id)",
        "WorkoutSet654.session_id == session_id",
        "func.count(WorkoutSet654.id)",
        "func.sum(WorkoutSet654.reps)",
        "func.sum(entry_volume)",
        "func.max(WorkoutSet654.weight_lb)",
        "active654(db)",
        "finish654(db=db)",
        "workout.id",
    ):
        if expected not in route:
            raise ValueError("Missing reviewed session protection: " + expected)
    for forbidden in (
        "db.add(", "db.delete(", "db.commit(", "Base.metadata",
        "ALTER TABLE", "DROP TABLE", "httpx", "requests.", "urlopen(",
        "get_engine(", "eval(", "exec(",
    ):
        if forbidden in route:
            raise ValueError("Unreviewed write/network/schema change: " + forbidden)
    if route.count("@router.post(") != 1 or route.count("@router.get(") != 1:
        raise ValueError("Unexpected new Workout routes")

    page = (root / "app/templates/workout_review663.html").read_text(
        encoding="utf-8"
    )
    for required in (
        "Workout Session Review", "workout.completed_at",
        "totals.machines", "totals.sets", "totals.reps", "totals.volume",
        "machine_rows", "row.name", "row.sets", "row.reps", "row.volume",
        'href="/workouts/sessions/{{ workout.id }}"',
        'href="/workouts/equipment/{{ row.equipment_id }}/progress"',
    ):
        if required not in page:
            raise ValueError("Review missing data or existing history link: " + required)
    for path, old_action in (
        ("app/templates/workouts654.html", "/workouts/finish"),
        ("app/templates/workout_quick659.html", "/workouts/quick/finish"),
    ):
        template = (root / path).read_text(encoding="utf-8")
        if ('action="' + old_action + '"') not in template:
            raise ValueError("Original Workout Finish action removed: " + path)
        if 'formaction="/workouts/finish-review"' not in template:
            raise ValueError("Finish-and-review action missing: " + path)
    print("WORKOUT_663_EXACT_SOURCE_ONLY_REVIEW=PASSED")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--base", required=True)
    parser.add_argument("--target", required=True)
    args = parser.parse_args()
    validate(args.root.resolve(), args.base, args.target)
