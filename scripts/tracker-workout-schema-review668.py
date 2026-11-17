#!/usr/bin/env python3
"""Release 668 strictly scoped additive-schema review, no database writes.

This reviewer is a prerequisite for the guarded runner's verified backup.
Only the expected new Workout 668 tables are authorized. Old schema sources
are immutable. Production must additionally verify the signed DEV approval.
"""
from __future__ import annotations

import argparse
import ast
from pathlib import Path
import re
import subprocess

BASE668 = "9baa03fb521573ba17ec1853fb85d40a22895336"
MODIFIED668 = frozenset({
    "app/main.py",
    "app/routers/calendar.py",
    "app/routers/workouts655.py",
    "app/routers/workouts658.py",
    "app/routers/workouts659.py",
    "app/routers/workouts663.py",
    "app/routers/workouts667.py",
    "app/templates/_workout_dashboard661.html",
    "app/templates/workout_backfill658.html",
    "app/templates/workout_program667.html",
    "app/templates/workout_quick659.html",
    "app/templates/workout_review663.html",
    "app/templates/workout_routine_detail655.html",
    "app/templates/workout_routines655.html",
    "scripts/tracker-release.sh",
    "scripts/tracker_prod_remote568.sh",
})
NEW668 = frozenset({
    "app/routers/workouts668.py",
    "app/static/js/tracker-workout-drafts668.js",
    "app/templates/workout_corrections668.html",
    "app/templates/workout_insights668.html",
    "app/templates/workout_schedule668.html",
    "app/workout_csv668.py",
    "app/workout_models668.py",
    "docs/release-668-deployment.md",
    "scripts/tracker-preview668.sh",
    "scripts/tracker-release-scoped668.sh",
    "scripts/tracker-release668.sh",
    "scripts/tracker-workout-schema-review668.py",
    "tests/test_calendar_sort668.py",
    "tests/test_workout_corrections668.py",
    "tests/test_workout_csv668.py",
    "tests/test_workout_csv_history668.py",
    "tests/test_workout_schedule668.py",
    "tests/test_workout_tools668.py",
})

EXPECTED_TABLES668 = {
    "WorkoutRoutineSchedule668": "workout_routine_schedule668",
    "WorkoutRoutineGroup668": "workout_routine_groups668",
    "WorkoutRoutineGroupMember668": "workout_routine_group_members668",
    "WorkoutSetCorrection668": "workout_set_corrections668",
}


def git(root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-c", f"safe.directory={root}", "-C", str(root), *args],
        text=True, capture_output=True, check=False,
    )
    if result.returncode:
        raise ValueError("Git exact-source review failed: " + result.stderr[:160])
    return result.stdout.strip()


def review668(root: Path, base: str, target: str) -> None:
    if base != BASE668 or not re.fullmatch(r"[0-9a-f]{40}", target):
        raise ValueError("Unexpected base or target commit")
    if git(root, "rev-parse", "HEAD") != target:
        raise ValueError("Candidate worktree must equal exact target")
    git(root, "merge-base", "--is-ancestor", base, target)
    changed = set(git(root, "diff", "--name-only", base, target).splitlines())
    allowed = MODIFIED668 | NEW668
    if changed != allowed:
        raise ValueError(f"Unexpected changed paths: {sorted(changed ^ allowed)!r}")
    for protected in (
        "app/db.py", "app/models.py", "app/migrations.py",
        "app/scoped_db390.py", "app/workout_models654.py",
        "app/workout_models655.py", "app/workout_models667.py",
        "app/workout_program667.py",
    ):
        if git(root, "rev-parse", f"{base}:{protected}") != git(
            root, "rev-parse", f"{target}:{protected}"
        ):
            raise ValueError("Historical schema, scope or frozen goals changed: " + protected)

    before = git(root, "show", f"{base}:app/main.py")
    after = (root / "app/main.py").read_text(encoding="utf-8")
    for expected in (
        "from . import workout_models668  # noqa: F401 - register additive Workout 668 tables\n",
        "from .routers import workouts668\n",
        "app.include_router(workouts668.router)\n",
    ):
        if expected in before or after.count(expected) != 1:
            raise ValueError("Unexpected additive model/route registration")
        after = after.replace(expected, "", 1)
    if after.strip() != before:
        raise ValueError("Unexpected app startup or authentication modification")

    source = (root / "app/workout_models668.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    classes = {}
    for node in tree.body:
        if not isinstance(node, ast.ClassDef):
            continue
        table_names = [
            assign.value.value for assign in node.body
            if isinstance(assign, ast.Assign)
            and isinstance(assign.value, ast.Constant)
            and isinstance(assign.value.value, str)
            if any(isinstance(target, ast.Name) and target.id == "__tablename__"
                   for target in assign.targets)
        ]
        if len(table_names) != 1:
            raise ValueError("Unexpected schema class declaration")
        classes[node.name] = table_names[0]
    if classes != EXPECTED_TABLES668:
        raise ValueError("Only the four reviewed additive Workout tables are permitted")
    required = (
        'ForeignKey("workout_routines655.id", ondelete="CASCADE")',
        'ForeignKey("workout_routine_items655.id", ondelete="CASCADE")',
        'ForeignKey("workout_sets654.id", ondelete="RESTRICT")',
        "ck_workout668_group_type",
        "ck_workout668_group_rounds",
        "ck_workout668_correction_reason",
        "uq_workout668_group_single_membership",
    )
    if any(fragment not in source for fragment in required):
        raise ValueError("Expected key, constraint or referential guard is missing")
    if re.search(r"(?i)\b(?:alter\s+table|drop\s+table|truncate\s+table|drop_all)\b", source):
        raise ValueError("Non-additive schema operation")
    runner = (root / "scripts/tracker-release.sh").read_text(encoding="utf-8")
    remote = (root / "scripts/tracker_prod_remote568.sh").read_text(encoding="utf-8")
    for marker in (
        "app/workout_models668.py", "--reviewed-workout-668",
        "REVIEWED_WORKOUT_668", "tracker-workout-schema-review668.py",
        "WORKOUT_668_SCHEMA_PROCEDURE=AUTHORIZED",
        "Schema changes require verified migration backup",
        "Verified database backup required for data migration",
    ):
        if marker not in runner:
            raise ValueError("Guarded DEV/PROD migration runner is incomplete: " + marker)
    if 'DEPLOY_EXTRA=(--reviewed-workout-668 --db-migration)' not in remote:
        raise ValueError("Signed PROD migration approval flag is missing")
    routes = (root / "app/routers/workouts668.py").read_text(encoding="utf-8")
    if "get_scoped_db390" not in routes or "db.commit()" not in routes:
        raise ValueError("Scoped Workout writes are unavailable")
    print("RELEASE_668_ADDITIVE_SCHEMA_SOURCE_REVIEW=PASSED")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--base", required=True)
    parser.add_argument("--target", required=True)
    args = parser.parse_args()
    review668(args.root.resolve(), args.base, args.target)
