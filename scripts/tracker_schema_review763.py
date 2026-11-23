#!/usr/bin/env python3
"""Review the five immutable additive Progress 762 tables for PROD 761 catch-up.

This validation is read-only; migration backups are separately mandated by
the signed deployment runner before any application code changes on PROD.
"""
from __future__ import annotations

import argparse
import ast
from pathlib import Path
import re
import subprocess
import sys

SHA = re.compile(r"[0-9a-f]{40}\Z")
PROD_761 = "04fd141daa17fd2055f9177527296eb9165a59d2"
APPROVED_762 = "35f6aa42aac648f3ed5af527620bd5f4b702b486"
EXPECTED = {
    "ProgressSettings762": "progress_settings762",
    "ProgressMeasure762": "progress_measurements762",
    "ProgressComposition762": "progress_composition762",
    "ProgressFunction762": "progress_function762",
    "ProgressMarker762": "progress_markers762",
}

def git(root, *args):
    p = subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True)
    if p.returncode:
        raise ValueError("Git source verification failed: " + args[0])
    return p.stdout.strip()

def verify(root: Path, base: str, target: str):
    if not SHA.fullmatch(base) or not SHA.fullmatch(target) or base != PROD_761:
        raise ValueError("Exact installed PROD 761 baseline required")
    if git(root, "rev-parse", "HEAD") != target:
        raise ValueError("Candidate worktree is not pinned target")
    git(root, "merge-base", "--is-ancestor", APPROVED_762, target)
    git(root, "merge-base", "--is-ancestor", base, target)
    source = "app/progress_models762.py"
    if git(root, "rev-parse", f"{APPROVED_762}:{source}") != git(root, "rev-parse", f"{target}:{source}"):
        raise ValueError("New progress table definitions differ from DEV-tested Release 762")
    touched = set(git(root, "diff", "--name-only", base, target).splitlines())
    if source not in touched or "app/main.py" not in touched:
        raise ValueError("Progress schema introduction is missing")
    for name in touched:
        if name in {"app/models.py", "app/db.py", "app/migrations.py"} or (
            name.startswith("app/") and (name.endswith("_models.py") or
            name.startswith("app/workout_models"))
        ):
            raise ValueError("Additional unreviewed schema change: " + name)
    tree = ast.parse((root / source).read_text(encoding="utf-8"))
    tables = {}
    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            assignments = [
                stmt for stmt in node.body if isinstance(stmt, ast.Assign)
                and any(isinstance(t, ast.Name) and t.id == "__tablename__"
                        for t in stmt.targets)
            ]
            if len(assignments) != 1 or not isinstance(assignments[0].value, ast.Constant):
                raise ValueError("Unreviewed table declaration")
            tables[node.name] = assignments[0].value.value
    if tables != EXPECTED:
        raise ValueError("Unexpected progress table set")
    main = (root / "app/main.py").read_text(encoding="utf-8")
    if "from . import progress_models762" not in main or "Base.metadata.create_all(engine)" not in main:
        raise ValueError("Progress schema registration or creation not present")

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--base", required=True)
    parser.add_argument("--target", required=True)
    args = parser.parse_args()
    try:
        verify(args.root, args.base, args.target)
    except (ValueError, OSError, SyntaxError) as exc:
        print("RELEASE_763_PROGRESS_SCHEMA_REVIEW=FAILED", file=sys.stderr)
        print("RELEASE_763_SCHEMA_GATE=" + str(exc), file=sys.stderr)
        return 2
    print("RELEASE_763_PROGRESS_SCHEMA_REVIEW=PASSED")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
