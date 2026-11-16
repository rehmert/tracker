#!/usr/bin/env python3
"""Release 652: fail-closed append-only schema review for managed COA test types.

Require exact base-vs-candidate diffs. Neither historical tables nor previously
recorded COA test_type strings are migrated or rewritten.
"""
import argparse
import ast
import subprocess
from pathlib import Path

ALLOWED = frozenset({
    "app/coa_catalog652.py",
    "app/main.py", "app/models.py",
    "app/routers/coa_test_type_catalog652.py", "app/routers/coas.py",
    "app/static/js/tracker-coa-multi651.js",
    "app/templates/coa_edit.html", "app/templates/coa_test_types_manage652.html",
    "app/templates/coas.html", "schema.sql",
    "docs/release-652-coa-catalog.md",
    "scripts/tracker-coa-scoped652.sh",
    "scripts/tracker-coa-preflight652.sh",
    "scripts/tracker-coa-dev652.sh",
    "scripts/tracker_schema_review652.py",
    "scripts/tracker-release.sh",
    "tests/test_coa_manage_catalog652.py",
    "scripts/tracker-coa-dev-backup652.py",
    "scripts/tracker-release-scoped652.sh",
    "scripts/tracker_dev_log577.py",
    "scripts/tracker_promote568.py",
    "tests/test_coa_test_type_picker646.py",
    "tests/test_release629_qa_cadence.py",
    "tests/test_release577_dev_receipt.py",
})


def git(root, *args):
    p = subprocess.run(
        ["git", "-c", f"safe.directory={root}", "-C", str(root), *args],
        text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
    )
    if p.returncode:
        raise ValueError("Git inspection failed: " + p.stderr[:200])
    return p.stdout


def review(root, base, target):
    changed = set(git(root, "diff", "--name-only", base, target).splitlines())
    if not changed or not changed <= ALLOWED:
        raise ValueError("Release 652 contains unreviewed paths: " +
                         ", ".join(sorted(changed - ALLOWED)))
    for required in ("app/models.py", "app/main.py", "schema.sql",
                     "app/coa_catalog652.py", "scripts/tracker-release.sh"):
        if required not in changed:
            raise ValueError("Missing reviewed change: " + required)

    before = git(root, "show", f"{base}:app/models.py")
    after = git(root, "show", f"{target}:app/models.py")
    start = "class CoaTestType652(Base):\n"
    tail = "\n\nclass CoaAttachment(Base):"
    if after.count(start) != 1 or before.count(start) or after.count(tail) != 1:
        raise ValueError("Unexpected catalog model placement")
    prefix, rest = after.split(start, 1)
    fragment, suffix = rest.split(tail, 1)
    if before != prefix + tail[2:] + suffix:
        raise ValueError("Existing SQLAlchemy models changed")
    parsed = ast.parse(start + fragment)
    if len(parsed.body) != 1 or not isinstance(parsed.body[0], ast.ClassDef):
        raise ValueError("Expected precisely one additive catalog model")
    klass = parsed.body[0]
    if klass.name != "CoaTestType652":
        raise ValueError("Unexpected catalog class")
    attrs = [node.target.id for node in klass.body
             if isinstance(node, ast.AnnAssign)
             and isinstance(node.target, ast.Name)]
    if attrs != ["id", "builtin_code", "label", "group_name", "active", "position"]:
        raise ValueError("Unexpected catalog columns")
    for field in (
        '    __tablename__ = "coa_test_type_catalog652"',
        '    id: Mapped[int] = mapped_column(primary_key=True)',
        '    builtin_code: Mapped[str | None] = mapped_column(String(80), unique=True, nullable=True)',
        '    label: Mapped[str] = mapped_column(String(100), nullable=False)',
        '    group_name: Mapped[str] = mapped_column(String(60), nullable=False)',
        '    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="1")',
        '    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")',
    ):
        if fragment.count(field) != 1:
            raise ValueError("Unexpected catalog DDL: " + field)

    main_before = git(root, "show", f"{base}:app/main.py")
    main_after = git(root, "show", f"{target}:app/main.py")
    new_init = ("    from .coa_catalog652 import seed_catalog652\n"
                "    seed_catalog652(engine)\n")
    new_import = "from .routers import coa_test_type_catalog652\n"
    new_include = "app.include_router(coa_test_type_catalog652.router)\n"
    for addition in (new_init, new_import, new_include):
        if main_after.count(addition) != 1 or addition in main_before:
            raise ValueError("Missing required startup/router catalog addition")
        main_after = main_after.replace(addition, "", 1)
    if main_after != main_before:
        raise ValueError("Unreviewed main.py change")

    schema_before = git(root, "show", f"{base}:schema.sql")
    schema_after = git(root, "show", f"{target}:schema.sql")
    expected = """
-- Release 652: user-maintained labels, stable built-in codes and custom IDs.
CREATE TABLE IF NOT EXISTS coa_test_type_catalog652 (
  id           INTEGER PRIMARY KEY,
  builtin_code VARCHAR(80) UNIQUE,
  label        VARCHAR(100) NOT NULL,
  group_name   VARCHAR(60) NOT NULL,
  active       BOOLEAN NOT NULL DEFAULT 1,
  position     INTEGER NOT NULL DEFAULT 0
);
"""
    if schema_after != schema_before + expected:
        raise ValueError("Unreviewed schema.sql changes")

    if git(root, "show", f"{target}:app/migrations.py") != \
       git(root, "show", f"{base}:app/migrations.py"):
        raise ValueError("Legacy migrations changed")
    print("COA_652_APPEND_ONLY_SCHEMA_REVIEW=PASSED")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--base", required=True)
    parser.add_argument("--target", required=True)
    a = parser.parse_args()
    review(a.root.resolve(), a.base, a.target)
