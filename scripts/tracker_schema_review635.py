#!/usr/bin/env python3
"""Release 635: fail-closed review of the *only* allowed additive schema change.

Invoked by the existing release worker before qualification or live mutation.
This review does not access the database; the worker subsequently requires and
restore-verifies a full SQLite backup before installation.
"""
from __future__ import annotations
import argparse
import ast
import subprocess
from pathlib import Path

ALLOWED = frozenset({
    "app/main.py",
    "app/models.py",
    "app/routers/regimen635.py",
    "app/templates/base.html",
    "app/templates/food.html",
    "app/templates/mobile_today509.html",
    "app/templates/regimen635.html",
    "docs/release-635-supplement-medication-regimen.md",
    "tests/test_release635_regimen.py",
    "scripts/tracker_schema_review635.py",
    "scripts/tracker-release.sh",
    "scripts/tracker_prod_remote568.sh",
    "tests/test_release635_schema_review.py",
    "tests/test_release627_csrf_remaining_negative_matrix.py",
    "tests/test_release627_csrf_reconciliation.py",
    "tests/test_release574_csrf_dynamic_shapes.py",
    "scripts/tracker_csrf_reconcile627.py",
})
TABLES = ("regimen_items635", "regimen_schedules635", "regimen_entries635")
CLASSES = ("RegimenItem", "RegimenSchedule", "RegimenEntry")


def git(root, *args):
    proc = subprocess.run(
        ["git", "-c", f"safe.directory={root}", "-C", str(root), *args],
        capture_output=True, text=True, check=False,
    )
    if proc.returncode:
        raise ValueError("Git inspection failed: " + proc.stderr.strip()[:200])
    return proc.stdout


def review(root, base, target):
    changed = frozenset(git(root, "diff", "--name-only", base, target).splitlines())
    if not changed or not changed <= ALLOWED:
        raise ValueError("Release 635 contains unapproved changed paths: " +
                         ", ".join(sorted(changed - ALLOWED)))
    if "app/models.py" not in changed:
        raise ValueError("Expected additive model change is missing.")
    baseline = git(root, "show", f"{base}:app/models.py")
    candidate = git(root, "show", f"{target}:app/models.py")
    # All pre-existing model source must remain exactly identical.
    if not candidate.startswith(baseline):
        raise ValueError("Release 635 modified existing model definitions.")
    extra = candidate[len(baseline):]
    tree = ast.parse(extra)
    classes = [node for node in tree.body if isinstance(node, ast.ClassDef)]
    if tuple(c.name for c in classes) != CLASSES:
        raise ValueError("Unexpected appended model classes.")
    if len(classes) != len(tree.body):
        raise ValueError("Only new model class declarations are permitted.")
    names = []
    for klass in classes:
        table = [
            node.value.value for node in klass.body
            if isinstance(node, ast.Assign)
            and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name)
            and node.targets[0].id == "__tablename__"
            and isinstance(node.value, ast.Constant)
            and isinstance(node.value.value, str)
        ]
        if len(table) != 1:
            raise ValueError("Missing or ambiguous table definition.")
        names.append(table[0])
    if tuple(names) != TABLES:
        raise ValueError("Unexpected table names.")
    if not all((name not in baseline) for name in TABLES):
        raise ValueError("New table names already appear in baseline model source.")
    # The core DB and migration scripts must not be part of the candidate diff.
    if changed & {
        "app/db.py", "app/migrations.py", "alembic.ini",
        "requirements.txt", "deploy/tracker.service",
    }:
        raise ValueError("Unreviewed migration or dependency change.")
    return changed


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--base", required=True)
    parser.add_argument("--target", required=True)
    args = parser.parse_args(argv)
    changed = review(args.root.resolve(), args.base, args.target)
    print("REGIMEN_635_SCHEMA_REVIEW=PASSED")
    print("REGIMEN_635_SCHEMA_ONLY_ADDITIVE=YES")
    print("REGIMEN_635_CHANGED_PATHS=" + str(len(changed)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
