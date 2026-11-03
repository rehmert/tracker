"""Ensure test acceleration keeps important safety guarantees."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_contention_still_checks_both_rejections():
    source = (
        ROOT / "tests/test_stage19_atomicity.py"
    ).read_text()

    assert (
        "def test_locked_writer_rejects_dose_edit_and_delete_without_mutation"
        in source
    )

    assert "BEGIN IMMEDIATE" in source
    assert "PRAGMA busy_timeout=150" in source

    assert "client.delete(" in source
    assert "status_code == 409" in source

    assert "blocker.rollback()" in source

    # The short timeout must never persist after the test.
    assert 'event.remove(' in source
    assert 'engine.dispose()' in source


def test_csrf_inventory_uses_one_module_fixture():
    source = (
        ROOT / "tests/test_csrf_readiness_inventory.py"
    ).read_text()

    assert '@pytest.fixture(scope="module")' in source

    assert source.count(
        "return audit.build(ROOT)"
    ) == 1

    assert "def test_known_routes_are_in_inventory" in source
    assert "def test_known_browser_paths_are_in_inventory" in source


def test_production_database_settings_are_untouched():
    source = (ROOT / "app/db.py").read_text()

    assert "PRAGMA journal_mode=WAL" in source
    assert "PRAGMA foreign_keys=ON" in source
    assert "busy_timeout=150" not in source


def test_full_release_regressions_still_required():
    source = (
        ROOT / "scripts/tracker-release.sh"
    ).read_text()

    assert 'timeout 1200 "$PY" -m pytest' in source
    assert "tracker-restore-verify.py" in source
    assert "tracker-runtime-smoke.py" in source
    assert "tracker-deployment-guard.py" in source
