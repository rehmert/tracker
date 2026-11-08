"""Keep every browser acceptance module inside guarded disposable QA."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
QUALIFIER = ROOT / "scripts/tracker-browser-qualify.sh"
RELEASE = ROOT / "scripts/tracker-release.sh"

ISOLATED_ROOT = (
    "tests/test_bulk_vial_browser.py",
    "tests/test_bulk_vial_guided_browser.py",
    "tests/test_bulk_delete_browser.py",
    "tests/test_purchase_vial_browser.py",
    "tests/test_stage33_browser_sorting.py",
    "tests/test_health_timeline_dates_browser.py",
    "tests/test_vitals_csv_browser.py",
)


def test_511_every_browser_module_in_disposable_qualification():
    source = QUALIFIER.read_text(encoding="utf-8")
    browser_paths = sorted((ROOT / "tests/browser").glob("test_*.py"))
    required = [str(path.relative_to(ROOT)) for path in browser_paths]
    required.extend(ISOLATED_ROOT)
    assert len(required) == len(set(required))
    for name in required:
        assert source.count(name) == 1, name


def test_511_all_legacy_browser_entry_points_delegate_to_disposable_qa():
    for path in (
        ROOT / "run_browser_tests.sh",
        ROOT / "tracker-test.sh",
        ROOT / "scripts/tracker-test-gate475.sh",
    ):
        source = path.read_text(encoding="utf-8")
        assert "tracker-test-gate475.sh" in source or "tracker-browser-qualify.sh" in source
        assert 'pytest -q tests/browser' not in source
    assert "TRACKER_BROWSER_CANDIDATE" in (
        ROOT / "scripts/tracker-test-gate475.sh"
    ).read_text(encoding="utf-8")
    assert "TRACKER_TEST_URL" not in (
        ROOT / "run_browser_tests.sh"
    ).read_text(encoding="utf-8")


def test_511_guarded_release_keeps_backend_and_browser_separate():
    source = RELEASE.read_text(encoding="utf-8")
    assert 'timeout 600 bash "$QA/scripts/tracker-browser-qualify.sh"' in source
    assert "--ignore=tests/browser" in source
    browser = QUALIFIER.read_text(encoding="utf-8")
    assert "DISPOSABLE_INVENTORY_FIXTURES=2" in browser
    assert 'TRACKER_DATA_DIR="$DATA"' in browser
    assert source.index("ISOLATED BROWSER QUALIFICATION") < source.index("COMPLETE REGRESSION SUITE")
