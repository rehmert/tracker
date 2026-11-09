"""Release 523: keep the one qualified feature set available in both instances.

This is a source contract supplementing the real TestClient and the explicit
disposable PROD-mode Chromium gate. It never accesses installed services.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

PARITY_GATE_MODULES = (
    "app/session_auth385.py",
    "app/unified_login473.py",
    "app/secondary_preview430.py",
    "app/user_accounts427.py",
    "app/secondary_provision479.py",
    "app/secondary_account_edit480.py",
    "app/routers/user_management479.py",
    "app/worker_inventory435.py",
    "app/worker_vital_write433.py",
    "app/worker_food_write456.py",
    "app/worker_dose_write434.py",
    "app/worker_supply438.py",
    "app/worker_supply_use439.py",
    "app/worker_reconstitution436.py",
    "app/worker_reconciliation437.py",
    "app/worker_saved_food457.py",
    "app/secondary_backup442.py",
    "app/secondary_backup_ops443.py",
    "app/secondary_backup472.py",
    "app/secondary_account_readiness465.py",
    "app/secondary_cutover466.py",
)


def test_523_no_permanent_dev_only_gates_in_shared_features():
    for name in PARITY_GATE_MODULES:
        source = (ROOT / name).read_text()
        assert "interactive_parity523" in source, name
        assert 'config.instance_label() == "DEV"' not in source, name
        assert 'config.instance_label() != "DEV"' not in source, name


def test_523_prod_requires_own_marker_and_explicit_opt_in():
    sessions = (ROOT / "app/session_auth385.py").read_text()
    gate = (ROOT / "app/instance_parity523.py").read_text()
    assert ".tracker-session-auth-prod523" in sessions
    assert "TRACKER_PROD_PARITY523" in gate
    assert '== "1"' in gate
    assert ".tracker-session-auth-dev" in sessions


def test_523_disposable_browser_tests_run_prod_not_dev():
    browser = (ROOT / "scripts/tracker-browser-qualify.sh").read_text()
    assert "ISOLATED_PROD_AUTH_BOOTSTRAP=VERIFIED" in browser
    assert "ISOLATED_PROD_LOGIN_READY=YES" in browser
    assert "TRACKER_INSTANCE=PROD" in browser
    assert "TRACKER_PROD_PARITY523=1" in browser
    assert "tests/test_prod_login_browser523.py" in browser
    assert "ISOLATED_PROD_SESSION_BROWSER=PASSED" in browser
    assert "TRACKER_BROWSER_QA_DATA_DIR" in browser


def test_523_prod_cutover_and_release_preserve_recovery():
    release = (ROOT / "scripts/tracker-release.sh").read_text()
    cutover = (ROOT / "scripts/tracker-prod-parity523.py").read_text()
    assert "=== VERIFIED PRIVATE PROD AUTH/USER BACKUP ===" in release
    assert 'scripts/tracker-prod-parity523.py" backup' in release
    assert "PROD_LOGIN_PARITY523=ENABLED" in cutover
    assert "PROD_PRIVATE_BACKUP=VERIFIED" in cutover
    assert "ROLLBACK: PROD session activation" in cutover
    assert "TRACKER_PASS" in cutover
    assert "TRACKER_PROD_PARITY523" in cutover
