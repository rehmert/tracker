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


# Release 521 reruns selected existing modules with strict CSRF enabled.
# A strict-only module must not be collected against the report-only server.
STRICT_PASS_MARKER = "# Release 521: a second browser gate"
STRICT_ONLY = frozenset({
    "tests/browser/test_strict_csrf521.py",
    # Release 579 gathers evidence only while the disposable candidate has
    # strict CSRF enabled, never on the report-only standard pass.
    "tests/browser/test_csrf_runtime579.py",
    "tests/browser/test_csrf_workflows580.py",
    "tests/browser/test_csrf_inventory581.py",
    "tests/browser/test_csrf_dose_lifecycle582.py",
    "tests/browser/test_csrf_preparations583.py",
    "tests/browser/test_csrf_bulk587.py",
    "tests/browser/test_csrf_multipart588.py",
})
STRICT_REPLAY = frozenset({
    "tests/browser/test_labs_native_https501.py",
    "tests/browser/test_food_labs_mutations500.py",
})


def test_511_every_browser_module_in_disposable_qualification():
    source = QUALIFIER.read_text(encoding="utf-8")
    assert source.count(STRICT_PASS_MARKER) == 1
    standard, strict = source.split(STRICT_PASS_MARKER, 1)
    # Release 589 intentionally replays the 587/588 modules in one
    # *targeted-only* batch. Count only the guarded full-mode source
    # when asserting each required browser module is scheduled once.
    batch_start = "# Release 589: one explicit fail-closed batch"
    batch_end = "# Combined Release 587–588: isolate bulk inventory browser writes"
    assert strict.count(batch_start) == 1
    assert strict.count(batch_end) == 1
    before_batch, tail = strict.split(batch_start, 1)
    targeted_batch, after_batch = tail.split(batch_end, 1)
    assert 'if [[ "$MODE" == targeted && "$TARGETED_MODULE" == csrf-batch589 ]]' in targeted_batch
    assert targeted_batch.count("run_isolated_browser_module") == 2
    assert targeted_batch.count("tests/browser/test_csrf_bulk587.py") == 1
    assert targeted_batch.count("tests/browser/test_csrf_multipart588.py") == 1
    assert "TARGETED_CSRF_BATCH589=PASSED" in targeted_batch
    assert 'ISOLATED_STRICT_CSRF_BROWSER=PASSED' not in targeted_batch
    strict = before_batch + batch_end + after_batch

    browser_paths = sorted((ROOT / "tests/browser").glob("test_*.py"))
    required = [str(path.relative_to(ROOT)) for path in browser_paths]
    required.extend(ISOLATED_ROOT)
    assert len(required) == len(set(required))

    for name in required:
        if name in STRICT_ONLY:
            assert standard.count(name) == 0, ("strict-only in standard pass", name)
            assert strict.count(name) == 1, ("strict-only gate missing", name)
        else:
            assert standard.count(name) == 1, ("standard gate missing", name)
            assert strict.count(name) == (1 if name in STRICT_REPLAY else 0), (
                "unexpected strict replay or missing coverage", name
            )

    assert STRICT_ONLY <= set(required)
    assert STRICT_REPLAY <= set(required)
    assert 'TRACKER_CSRF_ENFORCE=1' in strict
    assert 'TRACKER_TEST_STRICT_CSRF=1' in strict
    assert 'ISOLATED_STRICT_CSRF_READY=YES' in strict
    assert 'ISOLATED_STRICT_CSRF_BROWSER=PASSED' in strict


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
