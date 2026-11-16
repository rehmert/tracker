#!/usr/bin/env python3
"""Release 645: exact append-only schema review for COA default preference."""
import argparse
import ast
import subprocess
from pathlib import Path

ALLOWED = frozenset({
    "app/models.py", "app/routers/coas.py", "app/templates/coa_edit.html",
    "app/templates/vial_detail.html", "app/migrations.py", "schema.sql",
    "tests/test_release_350_353.py", "tests/test_release_354_357.py",
    "tests/browser/test_csrf_workflows580.py",
    "tests/test_browser_qualification511.py",
    "scripts/tracker-browser-qualify.sh",
    "tests/test_inventory_extensions.py", "tests/test_coa_endotoxins645.py",
    "scripts/tracker-release.sh", "scripts/tracker_prod_remote568.sh",
    "scripts/tracker_schema_review645.py", "scripts/tracker-coa-scoped645.sh",
    "scripts/tracker-coa-dev645.sh", "scripts/tracker-coa-preflight645.sh",
    "scripts/tracker-coa-attachment-audit645.py",
    "scripts/tracker-resume-evidence645.py",
    "scripts/tracker-attachment-integrity645.py",
    "scripts/tracker-prod-uploads-to-dev645.sh",
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
    prior_line = '    endotoxin_pct: Mapped[float | None] = mapped_column(Float, nullable=True)'
    replacement = (
        prior_line + '  # legacy percent; never reinterpret as EU/vial\n'
        '    endotoxin_eu_per_vial: Mapped[float | None] = mapped_column(Float, nullable=True)\n'
        '    endotoxin_result_kind: Mapped[str | None] = mapped_column(String(12), nullable=True)  # lt1, exact; NULL means legacy/unknown'
    )
    if prior.count(prior_line) != 1 or candidate.count(replacement) != 1:
        raise ValueError("Exact EU/vial model addition absent")
    normalized = candidate.replace(replacement, prior_line, 1)
    if not normalized.startswith(prior):
        raise ValueError("Existing model definitions changed beyond reviewed column")
    extra = normalized[len(prior):]
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
    # This release adds two nullable coas columns through the existing
    # non-destructive, idempotent migration hook. Never rewrite old percentages.
    migration_before = git(root, "show", f"{base}:app/migrations.py")
    migration_after = git(root, "show", f"{target}:app/migrations.py")
    migration_line = '                "endotoxin_pct": "FLOAT",'
    migration_add = migration_line + '\n                "endotoxin_eu_per_vial": "FLOAT",' + '\n                "endotoxin_result_kind": "VARCHAR(12)",'
    if (migration_before.count(migration_line) != 1
            or migration_after.count(migration_add) != 1
            or migration_after.replace(migration_add, migration_line, 1) != migration_before):
        raise ValueError("Unapproved migration changes")
    schema_before = git(root, "show", f"{base}:schema.sql")
    schema_after = git(root, "show", f"{target}:schema.sql")
    schema_line = '  endotoxin_pct           FLOAT,'
    schema_add = schema_line + '\n  endotoxin_eu_per_vial   FLOAT,' + '\n  endotoxin_result_kind  VARCHAR(12),'
    if (schema_before.count(schema_line) != 1
            or schema_after.count(schema_add) != 1
            or schema_after.replace(schema_add, schema_line, 1) != schema_before):
        raise ValueError("Unapproved schema documentation changes")
    if changed & {"app/db.py", "requirements.txt", "alembic.ini"}:
        raise ValueError("Unreviewed core migration files")
    print("COA_645_APPEND_ONLY_SCHEMA_REVIEW=PASSED")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--base", required=True)
    parser.add_argument("--target", required=True)
    a = parser.parse_args()
    review(a.root.resolve(), a.base, a.target)
