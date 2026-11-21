#!/usr/bin/env python3
"""Release 731: exact additive tablet-dose schema review, no live writes."""
from __future__ import annotations

import argparse
import ast
import subprocess
from pathlib import Path

DEV_BASE_730 = "13ed014d24ba5658a69ccb15b6d8e1a247c7575c"
ALLOWED = frozenset({
    "app/models.py",
    "app/regimen_tablets731.py",
    "app/routers/regimen635.py",
    "app/static/js/tracker-regimen-tablets731.js",
    "app/templates/regimen635.html",
    "docs/release-731-tablet-dose-tracking.md",
    "scripts/tracker-install731.sh",
    "scripts/tracker-qualify731.sh",
    "scripts/tracker-release-scoped731.sh",
    "scripts/tracker-release.sh",
    "scripts/tracker_schema_review731.py",
    "tests/browser/test_release731_tablet_tracking.py",
    "tests/test_release731_tablet_tracking.py",
    "tests/test_release731_schema_review.py",
})

TABLES = {
    "RegimenTabletSchedule731": (
        "regimen_tablet_schedule731", "schedule_id",
        ("tablet_strength_mg", "prescribed_dose_mg", "tablets_planned"),
        "regimen_schedules635.id",
    ),
    "RegimenTabletEntry731": (
        "regimen_tablet_entry731", "entry_id",
        ("tablet_strength_mg", "prescribed_dose_mg",
         "tablets_taken", "administered_dose_mg"),
        "regimen_entries635.id",
    ),
}


def git(root: Path, *args: str) -> str:
    command = ["git", "-c", "safe.directory=" + str(root),
               "-C", str(root), *args]
    result = subprocess.run(command, text=True, capture_output=True,
                            check=False)
    if result.returncode:
        raise ValueError("Git schema review command failed: " + args[0])
    return result.stdout.strip() if args[0] == "rev-parse" else result.stdout


def _annotation_names(node: ast.ClassDef) -> set[str]:
    return {
        entry.target.id for entry in node.body
        if isinstance(entry, ast.AnnAssign)
        and isinstance(entry.target, ast.Name)
    }


def _table_name(node: ast.ClassDef) -> str | None:
    for entry in node.body:
        if isinstance(entry, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == "__tablename__"
            for target in entry.targets
        ) and isinstance(entry.value, ast.Constant):
            return entry.value.value
    return None


def review(root: Path, base: str, target: str) -> None:
    root = root.resolve()
    # DEV is pinned at Release 730. PROD may still be on Release 727,
    # but must be an ancestor with identical old ORM schema source.
    git(root, "merge-base", "--is-ancestor", base, DEV_BASE_730)
    git(root, "merge-base", "--is-ancestor", DEV_BASE_730, target)
    old = git(root, "show", DEV_BASE_730 + ":app/models.py")
    old_at_installed_base = git(root, "show", base + ":app/models.py")
    if old_at_installed_base != old:
        raise ValueError("Historical installed schema is not the pinned 730 baseline")

    changed = set(
        git(root, "diff", "--name-only", DEV_BASE_730, target).splitlines()
    )
    if (not changed or "app/models.py" not in changed or
            not changed <= ALLOWED):
        raise ValueError("Unreviewed tablet release source changes")

    new = git(root, "show", target + ":app/models.py")
    previous = ast.parse(old)
    candidate = ast.parse(new)
    extra = [
        node for node in candidate.body
        if isinstance(node, ast.ClassDef) and node.name in TABLES
    ]
    if {node.name for node in extra} != set(TABLES) or len(extra) != 2:
        raise ValueError("Expected exactly two new tablet schema classes")

    numeric_import = 0
    for entry in candidate.body:
        if isinstance(entry, ast.ImportFrom) and entry.module == "sqlalchemy":
            numeric_import += sum(alias.name == "Numeric" for alias in entry.names)
            entry.names = [a for a in entry.names if a.name != "Numeric"]
    if numeric_import != 1:
        raise ValueError("Unexpected SQLAlchemy Numeric import")
    # Removing only the two reviewed classes and Numeric from the AST
    # must yield the exact old model syntax tree; no old table or column
    # is allowed to change.
    candidate.body = [node for node in candidate.body if node not in extra]
    if ast.dump(candidate, include_attributes=False) != ast.dump(
        previous, include_attributes=False
    ):
        raise ValueError("Existing ORM model source was modified")

    for model in extra:
        table, primary, fields, parent = TABLES[model.name]
        if _table_name(model) != table:
            raise ValueError("Unexpected new table")
        if _annotation_names(model) != set((primary, *fields)):
            raise ValueError("Unexpected new table columns")
        if any(isinstance(entry, (ast.FunctionDef, ast.AsyncFunctionDef))
               for entry in model.body):
            raise ValueError("Unexpected model methods")
        definition = ast.unparse(model)
        if "ForeignKey('" + parent + "', ondelete='CASCADE')" not in definition:
            raise ValueError("Missing constrained one-to-one parent foreign key")
        if "primary_key=True" not in definition:
            raise ValueError("Missing tablet record primary key")
        if definition.count("Numeric(12, 3)") + definition.count("Numeric(9, 3)") != len(fields):
            raise ValueError("Unexpected tablet dose precision")

    print("RELEASE_731_APPEND_ONLY_SCHEMA_REVIEW=PASSED")
    print("RELEASE_731_REVIEWED_TABLES=2")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--base", required=True)
    parser.add_argument("--target", required=True)
    args = parser.parse_args()
    review(args.root, args.base, args.target)


if __name__ == "__main__":
    main()
