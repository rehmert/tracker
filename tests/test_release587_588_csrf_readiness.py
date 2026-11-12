"""Combined 587–588: strict browser bulk scope, receipts, readiness & no rollout."""
from pathlib import Path
import ast
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
QUALIFIER = ROOT / "scripts/tracker-browser-qualify.sh"
PREFLIGHT = ROOT / "scripts/tracker-targeted-preflight584.sh"
BROWSER = ROOT / "tests/browser/test_csrf_bulk587.py"
REPORT = ROOT / "scripts/tracker_csrf_runtime_report587.py"
READINESS = ROOT / "scripts/tracker_csrf_readiness588.py"


def test_587_browser_gate_keeps_bulk_strict_only():
    script = QUALIFIER.read_text()
    standard, strict = script.split("# Release 521: a second browser gate", 1)
    assert standard.count("tests/browser/test_csrf_bulk587.py") == 0
    assert strict.count("tests/browser/test_csrf_bulk587.py") == 1
    assert 'test_(csrf_preparations583|form_overlap586|csrf_bulk587|csrf_multipart588)[.]py' in standard
    assert 'TARGETED_BULK587_PREFLIGHT=PASSED' in strict
    assert 'tracker_csrf_runtime_report587.py' in strict
    assert strict.index('tests/browser/test_csrf_bulk587.py') < strict.index(
        'tracker_csrf_runtime_report587.py'
    ) < strict.index('ISOLATED_STRICT_CSRF_BROWSER=PASSED')
    assert "tests/browser/test_csrf_bulk587.py" in PREFLIGHT.read_text()
    assert "tests/browser/test_csrf_multipart588.py" in PREFLIGHT.read_text()
    result = subprocess.run(["bash", "-n", str(QUALIFIER)], capture_output=True)
    assert result.returncode == 0


def test_587_bulk_browser_fixture_isolated_and_real_browser_fetch():
    browser = BROWSER.read_text()
    for needle in (
        'TRACKER_TEST_ISOLATED', 'TRACKER_TEST_STRICT_CSRF',
        'tracker-browser-qa', 'DATA.parent.parent == Path("/tmp").resolve()',
        'db_file', 'synthetic_vial', 'page.evaluate',
        "window.trackerCsrfToken", '"x-tracker-csrf-report"',
        'unsigned_status', '403',
        'native_bulk_form_submission_tested',
    ):
        # DB path has its own explicit variable name.
        assert needle in browser or needle == 'db_file' and 'path = (DATA / "tracker.db").resolve()' in browser, needle
    assert "Base.metadata.create_all" not in browser
    assert "SessionLocal" not in browser
    ast.parse(browser)


def test_587_receipts_schema_must_be_exactly_2_private_reports():
    text = REPORT.read_text()
    assert '{"http-bulk.json", "https-bulk.json"}' in text
    assert "0o600" in text
    assert "info.st_nlink != 1" in text
    assert '"native_bulk_form_submission_tested": False' in text
    assert 'CSRF_587_SCOPE=BULK_VIAL_FETCH_ONLY_NOT_GLOBAL_CLEARANCE' in text
    ast.parse(text)


def test_588_route_readiness_never_grants_global_csrf_clearance():
    source = READINESS.read_text()
    assert 'BLOCKED_INCOMPLETE_RUNTIME_CLEARANCE' in source
    assert '"strict_csrf_enforce_installed": False' in source
    assert '"global_enable_authorized": False' in source
    assert 'Secondary-account HTTP/HTTPS signed writes and cross-account isolation' in source
    assert 'CSRF_588_INSTALLED_ENFORCEMENT=UNCHANGED_REPORT_ONLY' in source
    assert 'runtime_verified_in_this_report": False' in source
    ast.parse(source)


def test_588_installed_enforcement_default_unmodified():
    csrf = (ROOT / "app/csrf_enforcement520.py").read_text()
    assert 'os.environ.get("TRACKER_CSRF_ENFORCE", "0") == "1"' in csrf
    assert 'TRACKER_CSRF_ENFORCE=1' not in PREFLIGHT.read_text()
