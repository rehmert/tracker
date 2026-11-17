#!/usr/bin/env python3
"""Release 667 reviewed append-only schema and exact allowed source changes.

The production deployment runner must execute this BEFORE applying a schema
change and must require the verified live-data migration backup. This script
does not modify any database or filesystem source.
"""
from __future__ import annotations

import argparse
import ast
import subprocess
from pathlib import Path

BASE667 = "4062afbc2ca4273d2fdadaab17c804c477a9fc08"

MODIFIED667 = frozenset({
    "app/main.py",
    "app/routers/workouts654.py",
    "app/routers/workouts655.py",
    "app/routers/workouts657.py",
    "app/routers/workouts659.py",
    "app/routers/workouts663.py",
    "app/templates/workouts654.html",
    "app/templates/workout_routine_detail655.html",
    "app/templates/workout_routines655.html",
    "app/templates/workout_quick659.html",
    "app/templates/workout_review663.html",
    "app/static/js/tracker-workouts659.js",
    "scripts/tracker-release.sh",
    "scripts/tracker_prod_remote568.sh",
})
NEW667 = frozenset({
    "app/workout_models667.py",
    "app/workout_program667.py",
    "app/routers/workouts667.py",
    "app/templates/workout_program667.html",
    "app/static/css/tracker-workout-program667.css",
    "app/static/js/tracker-workout-program667.js",
    "app/static/css/tracker-workout-gym667.css",
    "app/static/js/tracker-workout-gym667.js",
    "tests/test_workouts667.py",
    "tests/browser/test_workout_program667.py",
    "scripts/tracker-workout-dev667.sh",
    "scripts/tracker-workout-schema-review667.py",
    "scripts/tracker-release-scoped667.sh",
    "docs/release-667-workout-program.md",
})
ALLOWED667 = MODIFIED667 | NEW667

# Populated from GitHub's reviewed immutable Git blobs after final edits.
REVIEWED_BLOBS667 = {
}


def git(root: Path, *args: str) -> str:
    proc = subprocess.run(
        ["git", "-c", f"safe.directory={root}", "-C", str(root), *args],
        capture_output=True, text=True, check=False,
    )
    if proc.returncode:
        raise ValueError("Git review failed: " + proc.stderr[:180])
    return proc.stdout.strip()


def validate(root: Path, base: str, target: str) -> None:
    if base != BASE667 or git(root, "rev-parse", "HEAD") != target:
        raise ValueError("Candidate or reviewed Release 666 baseline mismatch")
    git(root, "merge-base", "--is-ancestor", base, target)
    changed = set(git(root, "diff", "--name-only", base, target).splitlines())
    if changed != ALLOWED667:
        raise ValueError("Unreviewed or missing Release 667 paths: " +
                         repr(sorted(changed ^ ALLOWED667)))
    if set(REVIEWED_BLOBS667) != MODIFIED667:
        raise ValueError("Unpinned existing-source review")
    for path, blobs in REVIEWED_BLOBS667.items():
        before = git(root, "rev-parse", f"{base}:{path}")
        after = git(root, "rev-parse", f"{target}:{path}")
        if (before, after) != tuple(blobs):
            raise ValueError("Existing source differs from reviewed Git blobs: " + path)

    for old in (
        "app/workout_models654.py", "app/workout_models655.py",
        "app/db.py", "app/models.py", "app/migrations.py",
    ):
        if git(root, "rev-parse", f"{base}:{old}") != git(root, "rev-parse", f"{target}:{old}"):
            raise ValueError("Existing schema was modified: " + old)

    main_before = git(root, "show", f"{base}:app/main.py")
    main_after = (root / "app/main.py").read_text(encoding="utf-8")
    for exact in (
        "from . import workout_models667  # noqa: F401 - register additive workout program tables\n",
        "from .routers import workouts667\n",
        "app.include_router(workouts667.router)\n",
    ):
        if exact in main_before or main_after.count(exact) != 1:
            raise ValueError("Unreviewed model or route registration")
        main_after = main_after.replace(exact, "", 1)
    if main_after.strip() != main_before:
        raise ValueError("Unexpected application startup change")

    model_source = (root / "app/workout_models667.py").read_text(encoding="utf-8")
    model_ast = ast.parse(model_source)
    declared = {}
    for node in model_ast.body:
        if not isinstance(node, ast.ClassDef):
            continue
        names = [
            st.value.value
            for st in node.body
            if isinstance(st, ast.Assign)
            and isinstance(st.value, ast.Constant)
            and isinstance(st.value.value, str)
            for name in st.targets
            if isinstance(name, ast.Name) and name.id == "__tablename__"
        ]
        if len(names) != 1:
            raise ValueError("Unreviewed new table declaration")
        declared[node.name] = names[0]
    expected = {
        "WorkoutRoutineConfig667": "workout_routine_config667",
        "WorkoutRoutineTarget667": "workout_routine_targets667",
        "WorkoutSessionTarget667": "workout_session_targets667",
        "WorkoutSetType667": "workout_set_types667",
    }
    if declared != expected:
        raise ValueError("Expected only four new additive Workout tables")
    for guard in (
        'ForeignKey("workout_routines655.id", ondelete="CASCADE")',
        'ForeignKey("workout_routine_items655.id", ondelete="CASCADE")',
        'ForeignKey("workout_sessions654.id", ondelete="CASCADE")',
        'ForeignKey("workout_equipment654.id", ondelete="RESTRICT")',
        'ForeignKey("workout_sets654.id", ondelete="CASCADE")',
        "ck_workout667_target_complete", "ck_workout667_set_type",
        "ck_workout667_routine_rest", "ck_workout667_session_rest",
    ):
        if guard not in model_source:
            raise ValueError("Missing additive FK/constraint: " + guard)
    for danger in ("ALTER TABLE", "DROP TABLE", "drop_all", "DELETE FROM"):
        if danger in model_source:
            raise ValueError("Non-additive operation in Workout667 models")

    runner = (root / "scripts/tracker-release.sh").read_text(encoding="utf-8")
    remote = (root / "scripts/tracker_prod_remote568.sh").read_text(
        encoding="utf-8"
    )
    for guard in (
        "app/workout_models667.py", "REVIEWED_WORKOUT_667",
        "--reviewed-workout-667", "tracker-workout-schema-review667.py",
        "WORKOUT_667_SCHEMA_PROCEDURE=AUTHORIZED",
        "Schema changes require verified migration backup",
        "Verified database backup required for data migration",
    ):
        if guard not in runner:
            raise ValueError("Schema release runner is missing: " + guard)
    for guard in (
        '[[ "$RELEASE" == 667 ]]',
        "DEPLOY_EXTRA=(--reviewed-workout-667 --db-migration)",
    ):
        if guard not in remote:
            raise ValueError("Signed PROD schema deployment guard missing: " + guard)

    routes = (root / "app/routers/workouts667.py").read_text(encoding="utf-8")
    for guard in (
        "get_scoped_db390",
        "WorkoutRoutineItem655.routine_id == routine_id",
        "parse_goal667(", "rest667(", "targets_json", "db.commit()",
    ):
        if guard not in routes:
            raise ValueError("Persistent program does not validate scoped writes: " + guard)
    program = (root / "app/workout_program667.py").read_text(encoding="utf-8")
    for guard in (
        "def snapshots667(", "def progress667(", "WorkoutSessionTarget667",
        "if kind != \"warmup\"", "min(matches, target.target_sets)",
    ):
        if guard not in program:
            raise ValueError("Frozen or actual-only goal calculation missing: " + guard)

    print("WORKOUT_667_EXACT_APPEND_ONLY_SCHEMA_AND_SOURCE_REVIEW=PASSED")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--base", required=True)
    parser.add_argument("--target", required=True)
    args = parser.parse_args()
    validate(args.root.resolve(), args.base, args.target)
