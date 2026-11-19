"""Release 705: offline artifact hash and fail-closed CSRF evidence contracts."""
from pathlib import Path
import os

import pytest

from scripts import tracker_dependency_lock705 as lock
from scripts import tracker_csrf_closeout705 as csrf

ROOT = Path(__file__).resolve().parents[1]


def test_705_csrf_source_inventory_does_not_claim_runtime_clearance():
    report = {
        "remaining_without_positive_source_witness": 51,
        "manual_review_items_unchanged": 110,
        "session_account_routes_not_certified": 6,
        "current_unsafe_routes": 202,
        "new_627_positive_routes": [
            {"full_dev_runtime_qualified": False} for _ in range(27)
        ],
        "remaining_route_workstreams": [{"workstream": "coas", "routes": 3}],
    }
    answer = csrf.summarize(report)
    assert answer["unmapped_positive_browser_routes"] == 51
    assert answer["manual_review_items"] == 110
    assert answer["global_enforcement_authorized"] is False
    assert answer["decision"] == "BLOCKED_PRESERVE_REPORT_ONLY"


def test_705_even_zero_source_gaps_do_not_authorize_enforcement(monkeypatch):
    monkeypatch.setattr(csrf, "build", lambda: {
        "remaining_without_positive_source_witness": 0,
        "manual_review_items_unchanged": 0,
        "session_account_routes_not_certified": 0,
        "current_unsafe_routes": 202,
        "new_627_positive_routes": [],
        "remaining_route_workstreams": [],
    })
    assert csrf.main(["--require-complete"]) == 1
    assert csrf.main([]) == 0


def test_705_offline_wheel_lock_round_trip_and_tamper_detection(tmp_path, monkeypatch):
    monkeypatch.setattr(lock, "all_pins",
                        lambda: {"alpha": "1.2", "pip": "25.1.1"})
    wheels = tmp_path / "wheels"
    wheels.mkdir()
    a = wheels / "alpha-1.2-py3-none-any.whl"
    a.write_bytes(b"synthetic alpha wheel")
    (wheels / "pip-25.1.1-py3-none-any.whl").write_bytes(b"synthetic pip wheel")
    output = tmp_path / "private"
    output.mkdir(mode=0o700)
    record = lock.create(wheels, output)
    assert [r["name"] for r in record["wheels"]] == ["alpha", "pip"]
    assert lock.verify(wheels, output) == record
    requirements = (output / lock.REQUIREMENTS_NAME).read_text()
    assert "--hash=sha256:" in requirements
    assert "--no-index" in requirements
    for filename in (lock.LOCK_NAME, lock.REQUIREMENTS_NAME):
        assert (output / filename).stat().st_mode & 0o077 == 0
    a.write_bytes(b"tampered")
    with pytest.raises(lock.LockError):
        lock.verify(wheels, output)


def test_705_wheel_lock_requires_complete_exact_pinset(tmp_path):
    wheels = tmp_path / "wheels"
    wheels.mkdir()
    (wheels / "alpha-1.2-py3-none-any.whl").write_bytes(b"synthetic")
    with pytest.raises(lock.LockError, match="exactly"):
        lock.inventory(wheels, {"alpha": "1.2", "pip": "25.1.1"})
    (wheels / "extra-1.0-py3-none-any.whl").write_bytes(b"extra")
    with pytest.raises(lock.LockError):
        lock.inventory(wheels, {"alpha": "1.2"})


def test_705_no_symlinks_or_public_receipts(tmp_path, monkeypatch):
    monkeypatch.setattr(lock, "all_pins", lambda: {"alpha": "1.2"})
    wheels = tmp_path / "wheels"
    wheels.mkdir()
    sample = wheels / "alpha-1.2-py3-none-any.whl"
    sample.write_bytes(b"synthetic")
    output = tmp_path / "output"
    output.mkdir()
    os.chmod(output, 0o755)
    with pytest.raises(lock.LockError):
        lock.create(wheels, output)
    os.chmod(output, 0o700)
    sample.unlink()
    sample.symlink_to(tmp_path / "untrusted")
    with pytest.raises(lock.LockError):
        lock.create(wheels, output)


def test_705_exact_post653_unqualified_routes_exist_in_current_source():
    from scripts.tracker_csrf_reconcile627 import (
        POST_654_PLUS_UNQUALIFIED_ROUTES,
        POST_652_UNQUALIFIED_CATALOG_ROUTES,
        POST_BASELINE_ADDITIONS,
    )
    from scripts.tracker_csrf_route_inventory620 import inventory

    declared = {
        (method, record["route"])
        for record in inventory(ROOT)
        for method in record["methods"]
        if record["route"] != "<dynamic>"
    }
    assert len(POST_652_UNQUALIFIED_CATALOG_ROUTES) == 3
    assert POST_652_UNQUALIFIED_CATALOG_ROUTES <= POST_BASELINE_ADDITIONS
    assert POST_652_UNQUALIFIED_CATALOG_ROUTES.isdisjoint(POST_654_PLUS_UNQUALIFIED_ROUTES)
    assert len(POST_654_PLUS_UNQUALIFIED_ROUTES) == 38
    assert POST_654_PLUS_UNQUALIFIED_ROUTES.isdisjoint(POST_BASELINE_ADDITIONS)
    assert all(method == "POST" for method, _ in POST_654_PLUS_UNQUALIFIED_ROUTES)
    assert POST_652_UNQUALIFIED_CATALOG_ROUTES <= declared
    assert POST_654_PLUS_UNQUALIFIED_ROUTES <= declared


def test_705_stays_read_only_and_preserves_historical_qualifiers():
    lock_source = (ROOT / "scripts/tracker_dependency_lock705.py").read_text()
    csrf_source = (ROOT / "scripts/tracker_csrf_closeout705.py").read_text()
    for source in (lock_source, csrf_source):
        for forbidden in (
            "systemctl restart", "git push", "/etc/tracker.env",
            "pip install -U", "TRACKER_CSRF_ENFORCE=1",
        ):
            assert forbidden not in source
    route_test = (ROOT / "tests/test_csrf_all_registered_negative705.py").read_text()
    assert "CRITICAL_WRITES = frozenset({" in route_test
    assert "if len(routes) < 120" not in route_test
    assert "if not isinstance(route, APIRoute)" not in route_test
    assert "def enumerate_unsafe_routes(route_items)" in route_test
    assert "from fastapi.routing import iter_route_contexts" in route_test
    assert "for context in iter_route_contexts(route_items):" in route_test
    assert "test_705_fastapi_0162_resolves_real_included_routers" in route_test
    assert "test_705_application_route_inventory_has_critical_writes" in route_test
    assert "missing = CRITICAL_WRITES - routes" in route_test
    assert "assert observed == {" in route_test
    assert 'signed_invalid.status_code == 422' in route_test
    gate = (ROOT / "scripts/tracker-release-scoped705.sh").read_text()
    for module in (
        "tests/test_release705_combined.py",
        "tests/test_csrf_all_registered_negative705.py",
        "tests/test_release627_csrf_reconciliation.py",
        "tests/test_release569_dependency_baseline.py",
        "tests/test_release570_freshenv.py",
    ):
        assert module in gate
    assert "RELEASE_705_ASGI_CSRF_NEGATIVE_CANARY=PASSED" in gate
    assert "RELEASE_705_BROWSER_MODULE_INVENTORY=PASSED" in gate
    assert gate.index("RELEASE_705_BROWSER_MODULE_INVENTORY=PASSED") < gate.index(
        "RELEASE_705_ASGI_CSRF_NEGATIVE_CANARY=PASSED"
    )
    standard = (ROOT / "scripts/tracker-browser-qualify.sh").read_text().split(
        "# Release 521: a second browser gate", 1
    )[0]
    previously_missing = (
        "tests/browser/test_consolidated_forms704.py",
        "tests/browser/test_css_parity699.py",
        "tests/browser/test_css_parity700.py",
        "tests/browser/test_daily_flow695.py",
        "tests/browser/test_integrated_flow696.py",
        "tests/browser/test_mobile_edit_actions703.py",
        "tests/browser/test_mobile_quick_actions701.py",
        "tests/browser/test_saved_food_mobile_actions702.py",
        "tests/browser/test_workout_calendar664.py",
        "tests/browser/test_workout_dashboard661.py",
        "tests/browser/test_workout_plan665.py",
        "tests/browser/test_workout_program667.py",
        "tests/browser/test_workout_targets666.py",
        "tests/browser/test_workouts_quick659.py",
        "tests/browser/test_workouts_quick662.py",
    )
    assert len(previously_missing) == 15
    for module in previously_missing:
        assert standard.count(module) == 1, module
    for number in (699, 700):
        # Browser registration is not executed parity QA without both roots.
        parity = (ROOT / f"tests/browser/test_css_parity{number}.py").read_text()
        assert f"TRACKER_CSS_PARITY{number}" in parity
        assert "pytest.mark.skipif" in parity
    assert "RELEASE_705_HISTORICAL_CSRF_RECONCILIATION=PASSED" in gate
    preview = (ROOT / "scripts/tracker-preview705.sh").read_text()
    assert "BASE=24cb9ec47417e001c3f96dfed630e3b8b0264d93" in preview
    assert "RELEASE_705_PREVIEW=PASSED_ISOLATED_NO_INSTALL" in preview
