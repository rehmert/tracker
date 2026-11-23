"""Release 760: reviewed exact PROD schema catch-up contract.

Read-only source inspection only; no production or private-data access.
"""
import subprocess
from pathlib import Path

from scripts.tracker_schema_review758 import MODEL_LINE, MIGRATION_LINE, exact_additive

ROOT = Path(__file__).resolve().parents[1]
PROD_BASE = "bb83f1a59de3defd5fe6d0bc83ad09ed4d0cfdac"
DEV_BASE = "eb1d3ab3c66aa8d2c8af8cc7ae4ed85bf4d2357d"


def show(sha, path):
    return subprocess.check_output(
        ["git", "-C", str(ROOT), "show", f"{sha}:{path}"],
        text=True,
    )


def test_760_only_nullable_production_date_schema_from_prod_755():
    target = subprocess.check_output(
        ["git", "-C", str(ROOT), "rev-parse", "HEAD"], text=True,
    ).strip()
    for path, addition in (
        ("app/models.py", MODEL_LINE),
        ("app/migrations.py", MIGRATION_LINE),
    ):
        assert exact_additive(show(PROD_BASE, path), show(target, path), addition)


def test_760_prod_script_exact_source_migration_gate():
    script = (ROOT / "scripts/tracker_prod_remote568.sh").read_text()
    assert 'elif [[ "$RELEASE" == 760 ]]; then' in script
    assert f'[[ "$BASE" == {PROD_BASE} ]]' in script
    assert 'DEPLOY_EXTRA=(--reviewed-vial-758 --db-migration)' in script
    assert '"${DEPLOY_EXTRA[@]}" 2>&1 | tee "$LOG"' in script
    runner = (ROOT / "scripts/tracker-release.sh").read_text()
    assert 'REVIEWED_VIAL_758' in runner
    assert 'tracker_schema_review758.py' in runner
    assert 'VIAL_758_SCHEMA_PROCEDURE=AUTHORIZED' in runner
    assert 'Schema changes require verified migration backup' in runner


def test_760_dev_install_is_tooling_only_with_no_db_override():
    install = (ROOT / "scripts/tracker-install760.sh").read_text()
    assert f"BASE={DEV_BASE}" in install
    assert "REF=release/760-prod-schema-catchup" in install
    assert "--db-migration" not in install
    assert "--reviewed-vial-758" not in install
    qualify = (ROOT / "scripts/tracker-qualify760.sh").read_text()
    assert "scripts/tracker_prod_remote568.sh" in qualify
    assert "scripts/tracker-release-scoped760.sh" in qualify
    assert "RELEASE_760_QUALIFICATION=PASSED_SCOPED_NO_DEPLOY" in qualify
