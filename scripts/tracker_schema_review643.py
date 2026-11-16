#!/usr/bin/env python3
"""Release 643: fail closed on any non-additive COA schema change."""
import argparse
import ast
import subprocess
from pathlib import Path

ALLOWED = frozenset({
    "app/models.py",
    "app/routers/coas.py",
    "app/templates/coa_edit.html",
    "app/templates/coas.html",
    "app/backup_references341.py",
    "scripts/tracker-release.sh",
    "scripts/tracker_prod_remote568.sh",
    "scripts/tracker_schema_review643.py",
    "tests/test_release643_coa_documents.py",
    "tests/browser/test_csrf_coa_lifecycle627.py",
    "tests/test_release643_schema_review.py",
    "tests/test_release635_schema_review.py",
    "docs/release-643-multiple-coa-test-documents.md",
})

def git(root, *args):
    result = subprocess.run(["git", "-c", f"safe.directory={root}",
                             "-C", str(root), *args],
                            capture_output=True, text=True, check=False)
    if result.returncode:
        raise ValueError("Git inspection failed: " + result.stderr[:200])
    return result.stdout

def review(root, base, target):
    changed = set(git(root, "diff", "--name-only", base, target).splitlines())
    if not changed or not changed <= ALLOWED:
        raise ValueError("Unapproved Release 643 paths: " +
                         ", ".join(sorted(changed - ALLOWED)))
    if "app/models.py" not in changed:
        raise ValueError("Expected one new COA attachment table")
    old = git(root, "show", f"{base}:app/models.py")
    new = git(root, "show", f"{target}:app/models.py")
    if not new.startswith(old):
        raise ValueError("Existing model definitions modified")
    nodes = ast.parse(new[len(old):]).body
    if len(nodes) != 1 or not isinstance(nodes[0], ast.ClassDef):
        raise ValueError("Exactly one new model class permitted")
    cls = nodes[0]
    if cls.name != "CoaDocument643":
        raise ValueError("Wrong model class")
    names = [
        node.value.value for node in cls.body
        if isinstance(node, ast.Assign) and len(node.targets) == 1
        and isinstance(node.targets[0], ast.Name)
        and node.targets[0].id == "__tablename__"
        and isinstance(node.value, ast.Constant)
        and isinstance(node.value.value, str)
    ]
    if names != ["coa_documents643"]:
        raise ValueError("Unexpected new table")
    for forbidden in ("app/db.py", "app/migrations.py", "requirements.txt",
                      "deploy/tracker.service"):
        if forbidden in changed:
            raise ValueError("Forbidden schema/configuration change")
    return changed

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--base", required=True)
    parser.add_argument("--target", required=True)
    args = parser.parse_args()
    changed = review(args.root.resolve(), args.base, args.target)
    print("COA_643_APPEND_ONLY_SCHEMA_REVIEW=PASSED")
    print("COA_643_CHANGED_PATHS=" + str(len(changed)))
