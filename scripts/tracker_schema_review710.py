#!/usr/bin/env python3
"""Release 710: exact additive schema review, no arbitrary migration approval.

Compare original Release 705 with the candidate, rejecting any unreviewed
changes in the model or migration files. This is a source-only review; the
isolated migration preservation tests run in the scoped qualification.
"""
from __future__ import annotations

import argparse
import ast
from pathlib import Path
import subprocess


def source(root: Path, ref: str, path: str) -> str:
    return subprocess.check_output(
        ["git", "-C", str(root), "show", f"{ref}:{path}"], text=True
    )


SUPPLY_FIELD = (
    '    blend_dose_id: Mapped[int | None] = mapped_column('
    'ForeignKey("blend_doses.id"), nullable=True)\n'
)
DRAW_FIELDS = (
    '    site: Mapped[str] = mapped_column(String(80), default="", server_default="")\n'
    '    entered_value: Mapped[float | None] = mapped_column(Float, nullable=True)\n'
    '    entered_unit: Mapped[str | None] = mapped_column(String(8), nullable=True)\n'
)
MIGRATION = '''        # Release 710: additive blend-dose parity with ordinary vial doses.
        # Old draws retain NULL entered-value/unit; the recorded volume is
        # still authoritative. Never create duplicate ordinary DoseLog rows.
        if "blend_doses" in tables:
            cols = {c["name"] for c in inspect(conn).get_columns("blend_doses")}
            for name, sql in {
                "site": "VARCHAR(80) NOT NULL DEFAULT ''",
                "entered_value": "FLOAT",
                "entered_unit": "VARCHAR(8)",
            }.items():
                if name not in cols:
                    conn.exec_driver_sql(f"ALTER TABLE blend_doses ADD COLUMN {name} {sql}")
        if "supply_usages" in tables:
            cols = {c["name"] for c in inspect(conn).get_columns("supply_usages")}
            if "blend_dose_id" not in cols:
                conn.exec_driver_sql(
                    "ALTER TABLE supply_usages ADD COLUMN blend_dose_id INTEGER "
                    "REFERENCES blend_doses(id) ON DELETE SET NULL"
                )
            conn.exec_driver_sql(
                "CREATE INDEX IF NOT EXISTS ix_supply_usages_blend_dose_id "
                "ON supply_usages(blend_dose_id)"
            )

'''


def check(root: Path, base: str, target: str) -> None:
    old_models = source(root, base, "app/models.py")
    new_models = source(root, target, "app/models.py")
    assert new_models.count(SUPPLY_FIELD) == 1, "Unapproved SupplyUsage field"
    assert new_models.count(DRAW_FIELDS) == 1, "Unapproved BlendDose fields"
    assert new_models.replace(SUPPLY_FIELD, "", 1).replace(DRAW_FIELDS, "", 1) == old_models, (
        "Models differ beyond the four reviewed additive fields"
    )
    old_migrations = source(root, base, "app/migrations.py")
    new_migrations = source(root, target, "app/migrations.py")
    assert new_migrations.count(MIGRATION) == 1, "Unexpected migration SQL"
    assert new_migrations.replace(MIGRATION, "", 1) == old_migrations, (
        "Migration source differs beyond the approved additive operations"
    )
    for path, text in (
        ("app/models.py", new_models),
        ("app/migrations.py", new_migrations),
    ):
        ast.parse(text, filename=path)
    print("RELEASE_710_SCHEMA_REVIEW=PASSED_EXACT_FOUR_ADDITIVE_FIELDS_AND_INDEX")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--base", required=True)
    parser.add_argument("--target", required=True)
    args = parser.parse_args()
    check(args.root.resolve(), args.base, args.target)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
