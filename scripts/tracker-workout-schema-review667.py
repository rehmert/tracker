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
    "app/main.py": (
        "43699dabf223f6ab95d018bcf5fb125800eca3e5",
        "5c4cf772a1b7ec47af2433c0598026ddee83738b",
    ),
    "app/routers/workouts654.py": (
        "034bdbc18c93757d7889516d44d00e1f906063b6",
        "d03884227def45bbfbdcd80a08f6fa83467ca77a",
    ),
    "app/routers/workouts655.py": (
        "0893c76ccfebe6ead1068ad1a714542f6fd2695e",
        "d25bd69bb755417f7c40ca34b6d7c68410a0d819",
    ),
    "app/routers/workouts657.py": (
        "eb5b3cf9cfea45ec956248af0cbb415a9786b60d",
        "ab0174dbae3cc11b6f91efb8f204a8819c692c9e",
    ),
    "app/routers/workouts659.py": (
        "bcbe4f5c43e0b242744822bb7e931b0c02937b58",
        "245b4608afb9e16a15ea88429c903998095e29a4",
    ),
    "app/routers/workouts663.py": (
        "195ddfe377bc0f9efbac95eebddfed9bcfdb7b3c",
        "daa829d5d2e64092a8dc398886f43b7fa0eefa0a",
    ),
    "app/templates/workouts654.html": (
        "43c21acd38124a59c02a34769e6461068b2d664e",
        "73fb3abe03bc69bbc20fa0812ef1cbef73c80936",
    ),
    "app/templates/workout_routine_detail655.html": (
        "2410447a25eaea4d4fdade6dd8a0861247621d4a",
        "1fb5a92af17c04b328c30ae465eda8170a28c1f0",
    ),
    "app/templates/workout_routines655.html": (
        "7f19df5dc6010ddd15332ac7a50afd01e0ee43c8",
        "b27b858cde180193a7e923c9ef4afb798a472302",
    ),
    "app/templates/workout_quick659.html": (
        "a8bce2a205be83fc6bfe8e72e1f9477fd3ff9f6b",
        "c41c86400276c7cb71ce7983449275f4d199558b",
    ),
    "app/templates/workout_review663.html": (
        "5ec088575d9210845175f6a12c049a9870f068e6",
        "183a8235995a4a639ba925ce56667edf31f913b3",
    ),
    "app/static/js/tracker-workouts659.js": (
        "de346e7c9f79f2c8f01842a2fb5c779835945ca9",
        "51dc5ccf294cf76d17ca5ae91321b52508e94289",
    ),
    "scripts/tracker-release.sh": (
        "a7d1b8b7b4193bf5e146553db898fbf79d7fac49",
        "6b3e52d898af77450e43a07a814dbf0ab77b07f4",
    ),
    "scripts/tracker_prod_remote568.sh": (
        "d8bb4c6c1e52755bc64ab53312b03c7e6b574a57",
        "07f36790a92a7f28cca314536af8a29b361b11f9",
    ),
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
