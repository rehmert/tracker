#!/usr/bin/env python3
"""Release 645: exact append-only schema review for COA default preference."""
import argparse
import ast
import subprocess
from pathlib import Path

ALLOWED = frozenset({
    "app/models.py", "app/routers/coas.py", "app/templates/coa_edit.html",
    "scripts/tracker-release.sh", "scripts/tracker_prod_remote568.sh",
    "scripts/tracker_schema_review645.py", "scripts/tracker-coa-scoped645.sh",
    "scripts/tracker-coa-dev645.sh", "scripts/tracker-coa-preflight645.sh",
    "tests/test_coa_document_defaults645.py", "tests/test_attachment_scope396.py",
    "scripts/tracker_csrf_reconcile627.py",
    "tests/test_release627_csrf_remaining_negative_matrix.py",
    "tests/test_release627_csrf_reconciliation.py",
    "tests/test_release597_purchase_supply_csrf.py",
    "tests/test_release574_csrf_dynamic_shapes.py",
    "tests/test_release596_vendor_multipart_csv.py",
    "tests/test_release593_pk_final_witnesses.py",
    "tests/test_release594_food_vendor_csrf.py",
    "tests/test_release595_food_vendor_lifecycle.py",
})


def git(root, *args):
    p = subprocess.run(["git", "-c", f"safe.directory={root}", "-C", str(root), *args],
                       text=True, capture_output=True, check=False)
    if p.returncode:
        raise ValueError("Git inspection failed: " + p.stderr[:200])
    return p.stdout


def review(root, base, target):
    changed = set(git(root, "diff", "--name-only", base, target).splitlines())
    if not changed or not changed <= ALLOWED:
        raise ValueError("Unapproved Release 645 changed paths: " +
                         ", ".join(sorted(changed - ALLOWED)))
    prior = git(root, "show", f"{base}:app/models.py")
    candidate = git(root, "show", f"{target}:app/models.py")
    if not candidate.startswith(prior):
        raise ValueError("Existing model definitions changed")
    extra = candidate[len(prior):]
    nodes = ast.parse(extra).body
    if len(nodes) != 1 or not isinstance(nodes[0], ast.ClassDef):
        raise ValueError("Only one appended SQLAlchemy model is allowed")
    cls = nodes[0]
    if cls.name != "CoaDefaultDocument645":
        raise ValueError("Unexpected additive model")
    table = [
        n.value.value for n in cls.body
        if isinstance(n, ast.Assign) and len(n.targets) == 1
        and isinstance(n.targets[0], ast.Name) and n.targets[0].id == "__tablename__"
        and isinstance(n.value, ast.Constant)
    ]
    if table != ["coa_default_documents645"]:
        raise ValueError("Unexpected table name")
    if "coa_default_documents645" in prior:
        raise ValueError("Table already exists")
    if len([n for n in cls.body if isinstance(n, ast.AnnAssign)]) != 2:
        raise ValueError("Only coa_id and attachment_id columns allowed")
    if "ForeignKey(\"coas.id\", ondelete=\"CASCADE\")" not in extra or \
       "ForeignKey(\"coa_attachments.id\", ondelete=\"CASCADE\")" not in extra:
        raise ValueError("Expected ownership and cascading foreign keys")
    if changed & {"app/db.py", "app/migrations.py", "requirements.txt", "alembic.ini"}:
        raise ValueError("Unreviewed core migration files")
    print("COA_645_APPEND_ONLY_SCHEMA_REVIEW=PASSED")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--base", required=True)
    parser.add_argument("--target", required=True)
    a = parser.parse_args()
    review(a.root.resolve(), a.base, a.target)
