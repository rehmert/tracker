#!/usr/bin/env python3
"""Release 655: exact-SHA review of new additive Workout routine schema.

Verifies the Release 654 baseline, explicit allowlisted changes, and exactly
three new routine tables. Does not touch the live database.
"""
from __future__ import annotations

import argparse
import ast
import subprocess
from pathlib import Path

ALLOWED = frozenset({
    "app/main.py",
    "app/workout_models655.py",
    "app/routers/workouts654.py",
    "app/routers/workouts655.py",
    "app/templates/workouts654.html",
    "app/templates/workout_routines655.html",
    "app/templates/workout_routine_detail655.html",
    "app/static/css/tracker-workouts655.css",
    "app/static/js/tracker-workouts655.js",
    "tests/test_workouts654.py",
    "tests/test_workouts655.py",
    "scripts/tracker-release.sh",
    "scripts/tracker-workout-schema-review655.py",
    "scripts/tracker-release-scoped655.sh",
    "scripts/tracker-workout-dev-backup655.py",
    "tests/test_workout_dev_backup655.py",
    "scripts/tracker-workout-dev655.sh",
    "docs/release-655-workout-routines.md",
})


def git(root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-c", f"safe.directory={root}", "-C", str(root), *args],
        capture_output=True, text=True, check=False,
    )
    if result.returncode:
        raise ValueError("Git inspection failed: " + result.stderr.strip()[:200])
    return result.stdout


def validate(root: Path, base: str, target: str) -> None:
    if git(root, "rev-parse", "HEAD").strip() != target:
        raise ValueError("Candidate checkout differs from pinned target")
    git(root, "merge-base", "--is-ancestor", base, target)
    paths = set(git(root, "diff", "--name-only", base, target).splitlines())
    required = {
        "app/main.py", "app/workout_models655.py",
        "app/routers/workouts655.py", "scripts/tracker-release.sh",
        "tests/test_workouts655.py",
    }
    if not required <= paths or not paths <= ALLOWED:
        raise ValueError("Unreviewed or missing changed paths: "
                         + repr(sorted((paths - ALLOWED) | (required - paths))))
    for legacy in (
        "app/workout_models654.py", "app/models.py", "app/db.py",
        "app/migrations.py", "schema.sql",
    ):
        if git(root, "show", f"{base}:{legacy}") != git(root, "show", f"{target}:{legacy}"):
            raise ValueError("Existing schema file changed unexpectedly: " + legacy)

    before = git(root, "show", f"{base}:app/main.py")
    after = git(root, "show", f"{target}:app/main.py")
    for addition in (
        "from . import workout_models655  # noqa: F401 - register routine tables\n",
        "from .routers import workouts655\n",
        "app.include_router(workouts655.router)\n",
    ):
        if addition in before or after.count(addition) != 1:
            raise ValueError("Unexpected application startup or router registration")
        after = after.replace(addition, "", 1)
    if after != before:
        raise ValueError("Unreviewed shared application startup changes")

    source = (root / "app/workout_models655.py").read_text(encoding="utf-8")
    model = ast.parse(source)
    actual = {}
    for node in model.body:
        if not isinstance(node, ast.ClassDef):
            continue
        values = [
            attr.value.value
            for attr in node.body
            if isinstance(attr, ast.Assign)
            for target_node in attr.targets
            if isinstance(target_node, ast.Name) and target_node.id == "__tablename__"
            if isinstance(attr.value, ast.Constant) and isinstance(attr.value.value, str)
        ]
        if len(values) != 1:
            raise ValueError("Unexpected routine table declaration")
        actual[node.name] = values[0]
    expected = {
        "WorkoutRoutine655": "workout_routines655",
        "WorkoutRoutineItem655": "workout_routine_items655",
        "WorkoutSessionRoutine655": "workout_session_routines655",
    }
    if actual != expected:
        raise ValueError("Expected precisely three new routine tables")
    for token in (
        'ForeignKey("workout_equipment654.id", ondelete="RESTRICT")',
        'ForeignKey("workout_sessions654.id", ondelete="CASCADE")',
        'ForeignKey("workout_routines655.id", ondelete="CASCADE")',
        'UniqueConstraint("routine_id", "equipment_id"',
    ):
        if token not in source:
            raise ValueError("Missing reviewed new-table foreign key or uniqueness constraint")
    if "drop_all" in source or "ALTER TABLE" in source or "DROP TABLE" in source:
        raise ValueError("Unreviewed schema operation")

    runner = (root / "scripts/tracker-release.sh").read_text(encoding="utf-8")
    for check in (
        "--reviewed-workout-655",
        "tracker-workout-schema-review655.py",
        "tracker-coa-dev-backup652.py",
        "REVIEWED_WORKOUT_655",
    ):
        if check not in runner:
            raise ValueError("Missing reviewed release-runner protection: " + check)
    print("WORKOUT_655_APPEND_ONLY_SCHEMA_REVIEW=PASSED")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--base", required=True)
    parser.add_argument("--target", required=True)
    args = parser.parse_args()
    validate(args.root.resolve(), args.base, args.target)


if __name__ == "__main__":
    main()
