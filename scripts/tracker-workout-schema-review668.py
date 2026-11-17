#!/usr/bin/env python3
"""Release 668: exact-SHA, allowlisted, append-only schema/source verification.

Mandatory before *either* DEV or signed PROD deployment. No mutations.
"""
from __future__ import annotations

import argparse
import ast
import subprocess
from pathlib import Path

BASE668 = "9baa03fb521573ba17ec1853fb85d40a22895336"

MODIFIED668 = frozenset({
    "app/main.py",
    "app/routers/dashboard.py",
    "app/routers/workouts654.py",
    "app/routers/workouts655.py",
    "app/routers/workouts656.py",
    "app/routers/workouts659.py",
    "app/routers/workouts664.py",
    "app/templates/_workout_dashboard661.html",
    "app/templates/workout_calendar664.html",
    "app/templates/workout_history654.html",
    "app/templates/workout_progress656.html",
    "app/templates/workout_quick659.html",
    "app/templates/workout_routine_detail655.html",
    "scripts/tracker-release.sh",
    "scripts/tracker_prod_remote568.sh",
})
NEW668 = frozenset({
    "app/workout_models668.py",
    "app/routers/workouts668_program.py",
    "app/routers/workouts668_history.py",
    "app/routers/workouts668_csv.py",
    "app/routers/workouts668_offline.py",
    "app/routers/workouts668_insights.py",
    "app/templates/workout_programs668.html",
    "app/templates/workout_insights668.html",
    "app/templates/workout_data668.html",
    "app/static/css/tracker-workout-advanced668.css",
    "app/static/js/tracker-workout-offline668.js",
    "app/static/js/tracker-workout-csv668.js",
    "tests/test_workouts668.py",
    "tests/browser/test_workout_advanced668.py",
    "scripts/tracker-workout-dev668.sh",
    "scripts/tracker-workout-promote668.sh",
    "scripts/tracker-release-scoped668.sh",
    "scripts/tracker-workout-schema-review668.py",
    "docs/release-668-advanced-workout.md",
})
ALLOWED668 = MODIFIED668 | NEW668

# Immutable reviewed before/after Git blob IDs of all previously deployed
# source files. Filled after final code review, before DEV qualification.
REVIEWED_BLOBS668 = {
    "app/main.py": (
        "5c4cf772a1b7ec47af2433c0598026ddee83738b",
        "aa05925cca87b439068a1df1cb1d2fcdc4ea6bef",
    ),
    "app/routers/dashboard.py": (
        "190267246b75af222c3906dbd2f4f8bed931fc80",
        "46e45cb51e93e5fc69282b9455b988f44c43932b",
    ),
    "app/routers/workouts654.py": (
        "d03884227def45bbfbdcd80a08f6fa83467ca77a",
        "cd5e60a50c69cdc63ef238de83cd2c1065168c54",
    ),
    "app/routers/workouts655.py": (
        "d25bd69bb755417f7c40ca34b6d7c68410a0d819",
        "071c60543932673fda3418d2be163197977ad4b7",
    ),
    "app/routers/workouts656.py": (
        "ab68c444ef9d9e05cfdd917da04d93feb80d4fd6",
        "46e0287b80e85710881ba977a12fda73fc05cfeb",
    ),
    "app/routers/workouts659.py": (
        "245b4608afb9e16a15ea88429c903998095e29a4",
        "b74ae8c854ddbdaa8cc287e312735e89731d6c86",
    ),
    "app/routers/workouts664.py": (
        "42e34c14b4359d683ca45975aea936460805c271",
        "5d8571dc0dc30ed8782ac1b22c1f4a59cede892b",
    ),
    "app/templates/_workout_dashboard661.html": (
        "72019f4e3ef7111b30fdcb9bf2383f960d62c6c4",
        "f98c30b7c564eaa9f6f0adb5dc08da1629050986",
    ),
    "app/templates/workout_calendar664.html": (
        "37588bc7140c71d18fc6b45e682544158aac8e13",
        "bcfbe6e60145bd5134347d0f7fc3b38ef919767a",
    ),
    "app/templates/workout_history654.html": (
        "39cbcd4c242e7804fc01a14b90a5c20b27df3046",
        "f57a1785ce423f32236fbd235970eff6a5a5c649",
    ),
    "app/templates/workout_progress656.html": (
        "921540b84db430134e64728b34c3224662ace65b",
        "100e3621576be6b82bc32772ebd2db54a598407f",
    ),
    "app/templates/workout_quick659.html": (
        "66ac42823e805ee811b3b097375fc6235b0b31af",
        "2f3217d089e0d27ecca1ebe821a93cf00c90fbde",
    ),
    "app/templates/workout_routine_detail655.html": (
        "1fb5a92af17c04b328c30ae465eda8170a28c1f0",
        "0d2a2025e38afa1092269b36ecd123d2773f682e",
    ),
    "scripts/tracker-release.sh": (
        "6b3e52d898af77450e43a07a814dbf0ab77b07f4",
        "7b0e905ea8084d363355f4eb5987aa7cf6c7cbda",
    ),
    "scripts/tracker_prod_remote568.sh": (
        "07f36790a92a7f28cca314536af8a29b361b11f9",
        "2ac0a9969d567cffe8e6b50718d106ce0bcdf41f",
    ),
}


def git(root: Path, *args: str) -> str:
    proc = subprocess.run(
        ["git", "-c", f"safe.directory={root}", "-C", str(root), *args],
        text=True, capture_output=True, check=False,
    )
    if proc.returncode:
        raise ValueError("Git object review failed: " + proc.stderr.strip()[:220])
    return proc.stdout.strip()


def validate(root: Path, base: str, target: str):
    if base != BASE668 or git(root, "rev-parse", "HEAD") != target:
        raise ValueError("Unexpected baseline or exact candidate checkout")
    git(root, "merge-base", "--is-ancestor", base, target)
    paths = set(git(root, "diff", "--name-only", base, target).splitlines())
    if paths != ALLOWED668:
        raise ValueError("Unreviewed or missing Release 668 changed path(s): " +
                         repr(sorted(paths ^ ALLOWED668)))
    if set(REVIEWED_BLOBS668) != MODIFIED668:
        raise ValueError("Missing exact Git pins for previously deployed files")
    for path, expected in REVIEWED_BLOBS668.items():
        before = git(root, "rev-parse", f"{base}:{path}")
        after = git(root, "rev-parse", f"{target}:{path}")
        if (before, after) != tuple(expected):
            raise ValueError("Unreviewed modified legacy Git blob: " + path)
    for unchanged in (
        "app/workout_models654.py",
        "app/workout_models655.py",
        "app/workout_models667.py",
        "app/workout_program667.py",
        "app/db.py", "app/models.py", "app/migrations.py",
        "app/session_auth385.py", "app/scoped_db390.py",
    ):
        if git(root, "rev-parse", f"{base}:{unchanged}") != git(root, "rev-parse", f"{target}:{unchanged}"):
            raise ValueError("Previously deployed schema/security code was modified: " + unchanged)

    old_main = git(root, "show", f"{base}:app/main.py")
    new_main = (root / "app/main.py").read_text(encoding="utf-8")
    for line in (
        "from . import workout_models668  # noqa: F401 - register additive advanced workout tables\n",
        "from .routers import workouts668_program, workouts668_history, workouts668_csv, workouts668_offline, workouts668_insights\n",
        "app.include_router(workouts668_program.router)\n",
        "app.include_router(workouts668_history.router)\n",
        "app.include_router(workouts668_csv.router)\n",
        "app.include_router(workouts668_offline.router)\n",
        "app.include_router(workouts668_insights.router)\n",
    ):
        if line in old_main or new_main.count(line) != 1:
            raise ValueError("Unexpected application model/router change")
        new_main = new_main.replace(line, "", 1)
    if new_main.strip() != old_main:
        raise ValueError("Unexpected shared application startup change")

    model_source = (root / "app/workout_models668.py").read_text(encoding="utf-8")
    classes = {}
    for node in ast.parse(model_source).body:
        if not isinstance(node, ast.ClassDef):
            continue
        names = [
            stmt.value.value for stmt in node.body
            if isinstance(stmt, ast.Assign)
            and isinstance(stmt.value, ast.Constant)
            and isinstance(stmt.value.value, str)
            for lhs in stmt.targets
            if isinstance(lhs, ast.Name) and lhs.id == "__tablename__"
        ]
        if len(names) != 1:
            raise ValueError("Unexpected table declaration")
        classes[node.name] = names[0]
    required_tables = {
        "WorkoutTrainingDay668": "workout_training_days668",
        "WorkoutRoutineGroup668": "workout_routine_groups668",
        "WorkoutSessionSubstitution668": "workout_session_substitutions668",
        "WorkoutSetAudit668": "workout_set_audit668",
        "WorkoutLoadSemantics668": "workout_load_semantics668",
        "WorkoutImportReceipt668": "workout_import_receipts668",
        "WorkoutOfflineReceipt668": "workout_offline_receipts668",
    }
    if classes != required_tables:
        raise ValueError("Expected exactly seven additive advanced Workout tables")
    for guard in (
        'ForeignKey("workout_routines655.id", ondelete="CASCADE")',
        'ForeignKey("workout_routine_items655.id", ondelete="CASCADE")',
        'ForeignKey("workout_sessions654.id", ondelete="CASCADE")',
        'ForeignKey("workout_equipment654.id", ondelete="RESTRICT")',
        "set_id: Mapped[int] = mapped_column(Integer, nullable=False)",
        "ck_workout668_weekday", "ck_workout668_group_mode",
        "ck_workout668_sub_distinct", "ck_workout668_audit_action",
        "ck_workout668_load_mode",
    ):
        if guard not in model_source:
            raise ValueError("Missing reviewed table constraint: " + guard)
    for dangerous in ("drop_all", "ALTER TABLE", "DROP TABLE", "DELETE FROM"):
        if dangerous in model_source:
            raise ValueError("Non-additive operation in Workout668 models")

    runner = (root / "scripts/tracker-release.sh").read_text(encoding="utf-8")
    remote = (root / "scripts/tracker_prod_remote568.sh").read_text(encoding="utf-8")
    for guard in (
        "app/workout_models668.py", "REVIEWED_WORKOUT_668",
        "--reviewed-workout-668", "tracker-workout-schema-review668.py",
        "WORKOUT_668_SCHEMA_PROCEDURE=AUTHORIZED",
        "Schema changes require verified migration backup",
        "Verified database backup required for data migration",
        "REF\" == release/668-advanced-workout",
    ):
        if guard not in runner:
            raise ValueError("Release 668 schema protection missing: " + guard)
    for guard in (
        '[[ "$RELEASE" == 668 ]]',
        "DEPLOY_EXTRA=(--reviewed-workout-668 --db-migration)",
    ):
        if guard not in remote:
            raise ValueError("Signed PROD migration flags missing: " + guard)
    for router in (
        "workouts668_program.py", "workouts668_history.py",
        "workouts668_csv.py", "workouts668_offline.py",
        "workouts668_insights.py",
    ):
        text = (root / "app/routers" / router).read_text(encoding="utf-8")
        if "get_scoped_db390" not in text:
            raise ValueError("Unscoped new Workout router: " + router)
    offline = (root / "app/routers/workouts668_offline.py").read_text(encoding="utf-8")
    for guard in (
        "UUID(token)", "active.id != session_id", "WorkoutOfflineReceipt668(",
        "db.commit()", "IntegrityError",
    ):
        if guard not in offline:
            raise ValueError("Missing safe idempotent offline replay: " + guard)
    audit = (root / "app/routers/workouts668_history.py").read_text(encoding="utf-8")
    for guard in ("before_json=", "after_json=", 'confirm_delete != "yes"', "db.commit()"):
        if guard not in audit:
            raise ValueError("Missing append-only historical correction audit: " + guard)
    print("WORKOUT_668_EXACT_ADD_ONLY_SCHEMA_AND_SOURCE_REVIEW=PASSED")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--base", required=True)
    parser.add_argument("--target", required=True)
    args = parser.parse_args()
    validate(args.root.resolve(), args.base, args.target)
