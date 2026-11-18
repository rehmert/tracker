#!/usr/bin/env python3
"""Release 691: reject any schema delta beyond two additive COA attachment fields."""
from __future__ import annotations

import argparse
import ast
from pathlib import Path
import subprocess


def source(root: Path, ref: str, path: str) -> str:
    return subprocess.check_output(
        ["git", "-C", str(root), "show", f"{ref}:{path}"], text=True,
    )


def check(root: Path, base: str, target: str) -> None:
    old_model = source(root, base, "app/models.py")
    new_model = source(root, target, "app/models.py")
    new_fields = (
        '    job_id: Mapped[str] = mapped_column(String(120), nullable=False, default="", server_default="")\n'
        '    verify_code: Mapped[str] = mapped_column(String(120), nullable=False, default="", server_default="")\n'
    )
    anchor = 'class CoaAttachment(Base):'
    assert new_model.count(anchor) == old_model.count(anchor) == 1
    attachment = new_model.split(anchor, 1)[1].split("class CoaRevision(Base):", 1)[0]
    assert attachment.count(new_fields) == 1, "Attachment fields differ from approval"
    assert new_model.replace(new_fields, "", 1) == old_model, (
        "Model changes exceed the two approved attachment identifier columns"
    )
    old_migration = source(root, base, "app/migrations.py")
    new_migration = source(root, target, "app/migrations.py")
    migration = '''
        # Release 691: additive, idempotent per-document identifiers. Original
        # COA files continue to use coas.job_id / coas.verify_code.
        if "coa_attachments" in tables:
            columns = {c["name"] for c in inspect(conn).get_columns("coa_attachments")}
            for name in ("job_id", "verify_code"):
                if name not in columns:
                    conn.exec_driver_sql(
                        f"ALTER TABLE coa_attachments ADD COLUMN {name} VARCHAR(120) NOT NULL DEFAULT ''"
                    )
'''
    assert new_migration.count(migration) == 1, (
        "Migration not the expected additive two-column operation"
    )
    assert new_migration.replace("\n" + migration, "", 1) == old_migration, (
        "Unapproved SQLite migration source changes"
    )
    ast.parse(new_model)
    ast.parse(new_migration)
    print("COA_691_SCHEMA_REVIEW=PASSED_EXACT_TWO_ADDITIVE_COLUMNS")


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--root", type=Path, required=True)
    p.add_argument("--base", required=True)
    p.add_argument("--target", required=True)
    args = p.parse_args()
    check(args.root.resolve(), args.base, args.target)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
