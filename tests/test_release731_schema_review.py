"""Release 731: reviewed additive schema and signed deployer migration gate."""
from pathlib import Path

import pytest
from sqlalchemy import create_engine, inspect

from app.db import Base
from app.models import RegimenTabletEntry731, RegimenTabletSchedule731
from scripts import tracker_schema_review731 as schema

ROOT = Path(__file__).resolve().parents[1]
PROD_727 = "3718936aedfcb1b8fe243c86fe6fc7e06a7a41d2"


def test_731_exact_additive_schema_from_dev_and_older_prod_base():
    schema.review(ROOT, schema.DEV_BASE_730, "HEAD")
    schema.review(ROOT, PROD_727, "HEAD")


def test_731_invalid_and_unrelated_schema_bases_fail_closed():
    with pytest.raises(ValueError):
        schema.review(ROOT, "HEAD", "HEAD")
    with pytest.raises(ValueError):
        schema.review(ROOT, "NOT_A_SHA", "HEAD")


def test_731_two_additive_tables_and_existing_regimen_schema_intact():
    engine = create_engine("sqlite://")
    try:
        Base.metadata.create_all(engine)
        inspector = inspect(engine)
        expected = {
            "regimen_tablet_schedule731": {
                "schedule_id", "tablet_strength_mg",
                "prescribed_dose_mg", "tablets_planned",
            },
            "regimen_tablet_entry731": {
                "entry_id", "tablet_strength_mg",
                "prescribed_dose_mg", "tablets_taken",
                "administered_dose_mg",
            },
        }
        for table, columns in expected.items():
            assert table in inspector.get_table_names()
            assert {field["name"] for field in inspector.get_columns(table)} == columns
            assert len(inspector.get_pk_constraint(table)["constrained_columns"]) == 1
            assert len(inspector.get_foreign_keys(table)) == 1
            assert inspector.get_foreign_keys(table)[0]["options"].get("ondelete") == "CASCADE"
        for table in ("regimen_items635", "regimen_schedules635",
                      "regimen_entries635", "regimen_product_facts639"):
            assert table in inspector.get_table_names()
        assert RegimenTabletEntry731.__tablename__ == "regimen_tablet_entry731"
        assert RegimenTabletSchedule731.__tablename__ == "regimen_tablet_schedule731"
    finally:
        engine.dispose()


def test_731_signed_runner_requires_reviewed_schema_and_verified_backup():
    runner = (ROOT / "scripts/tracker-release.sh").read_text()
    installer = (ROOT / "scripts/tracker-install731.sh").read_text()
    scoped = (ROOT / "scripts/tracker-release-scoped731.sh").read_text()
    qualification = (ROOT / "scripts/tracker-qualify731.sh").read_text()

    for expected in (
        '--reviewed-tablet-731', "REVIEWED_TABLET_731",
        "REGIMEN_731_SCHEMA_PROCEDURE=AUTHORIZED",
        "scripts/tracker_schema_review731.py",
        '"$REVIEWED_TABLET_731" == 0 || "$DB_MIGRATION" == 1',
        'Release 731 must be the sole reviewed schema flag',
        '[[ $# -ge 12 && $# -le 21 ]]',
        '"$REVIEWED_BLEND_710" "$REVIEWED_TABLET_731"',
        '=== Verified database backup required for data migration ===',
    ):
        assert expected in runner, expected
    assert "--db-migration --reviewed-tablet-731" in installer
    assert "tracker_schema_review731.py" in qualification
    assert "RELEASE_731_STANDALONE_SCHEMA_REVIEW=PASSED" in qualification
    assert "tests/test_release731_schema_review.py" in scoped
