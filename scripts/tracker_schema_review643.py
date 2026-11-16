#!/usr/bin/env python3
"""Release 643: fail-closed, additive-only COA attachment schema review."""
from __future__ import annotations

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
    "tests/test_attachment_scope396.py",
    "tests/test_coa_multiple_documents.py",
    "scripts/tracker-coa-qualify643.sh",
    "scripts/tracker-coa-schema-rehearsal643.sh",
    "scripts/tracker-coa-deploy-dev643.sh",
    "scripts/tracker-coa-scoped643.sh",
    "scripts/tracker_schema_review643.py",
    "scripts/tracker-release.sh",
    "scripts/tracker_prod_remote568.sh",
    "scripts/tracker_csrf_reconcile627.py",
    "tests/test_release627_csrf_remaining_negative_matrix.py",
    "tests/test_release627_csrf_reconciliation.py",
    "tests/test_release597_purchase_supply_csrf.py",
    "tests/test_release574_csrf_dynamic_shapes.py",
    "tests/test_release596_vendor_multipart_csv.py",
    "tests/test_release593_pk_final_witnesses.py",
    "tests/test_release594_food_vendor_csrf.py",
    "tests/test_release595_food_vendor_lifecycle.py",
    "scripts/tracker-coa-preflight644.sh",
    "scripts/tracker-coa-deploy-dev644.sh",
})

RELATIONSHIP = (
    '    attachments: Mapped[list["CoaAttachment"]] = '
    'relationship("CoaAttachment", back_populates="coa", '
    'cascade="all, delete-orphan", order_by="CoaAttachment.id")\n'
)


def git(root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-c", f"safe.directory={root}", "-C", str(root), *args],
        capture_output=True, text=True, check=False,
    )
    if result.returncode:
        raise ValueError("Git inspection failed: " + result.stderr[:250])
    return result.stdout


def review(root: Path, base: str, target: str) -> None:
    changed = set(git(root, "diff", "--name-only", base, target).splitlines())
    if not changed or not changed <= ALLOWED:
        raise ValueError("Unapproved Release 643 paths: " + ", ".join(sorted(changed - ALLOWED)))
    if not {"app/models.py", "scripts/tracker_schema_review643.py"} <= changed:
        raise ValueError("Expected schema model and review are absent")
    existing = git(root, "show", f"{base}:app/models.py")
    candidate = git(root, "show", f"{target}:app/models.py")
    start = "\n\nclass CoaAttachment(Base):"
    end = "\n\nclass CoaRevision(Base):"
    if candidate.count(start) != 1 or candidate.count(end) != 1:
        raise ValueError("Unexpected COA attachment model layout")
    prefix, remainder = candidate.split(start, 1)
    addition, suffix = remainder.split(end, 1)
    tree = ast.parse("class CoaAttachment(Base):" + addition)
    if len(tree.body) != 1 or not isinstance(tree.body[0], ast.ClassDef):
        raise ValueError("Unexpected additional model code")
    tables = [
        node.value.value for node in tree.body[0].body
        if isinstance(node, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id == "__tablename__"
                for target in node.targets)
        and isinstance(node.value, ast.Constant)
    ]
    if tables != ["coa_attachments"]:
        raise ValueError("Unapproved table definition")
    reconstructed = prefix + end + suffix
    # The additive class insertion included one additional separator newline.
    reconstructed = reconstructed.replace('\n\n\n\nclass CoaRevision(Base):',
                                          '\n\n\nclass CoaRevision(Base):', 1)
    if reconstructed.count(RELATIONSHIP) != 1:
        raise ValueError("Unexpected relationship definition")
    reconstructed = reconstructed.replace(RELATIONSHIP, "", 1)
    if reconstructed != existing:
        raise ValueError("Existing model definitions changed beyond the reviewed relationship")
    if "coa_attachments" in existing:
        raise ValueError("COA attachments table already present in baseline")
    if changed & {"app/db.py", "app/migrations.py", "requirements.txt", "alembic.ini"}:
        raise ValueError("Unreviewed core migration change")
    print("COA_643_ADDITIVE_SCHEMA_REVIEW=PASSED")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--base", required=True)
    parser.add_argument("--target", required=True)
    args = parser.parse_args()
    review(args.root.resolve(), args.base, args.target)
