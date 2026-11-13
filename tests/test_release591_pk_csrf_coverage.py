"""Release 591: PK lifecycle witness contract, scope, and no false clearance."""
from pathlib import Path
import ast
import re
import subprocess
import sys

from scripts import tracker_csrf_gap_plan590 as gap
from scripts import tracker_csrf_readiness588 as readiness

ROOT = Path(__file__).resolve().parents[1]
BROWSER = ROOT / "tests/browser/test_strict_csrf521.py"
RUNNER = ROOT / "scripts/tracker-browser-qualify.sh"

PK_ROUTES = frozenset({
    ("POST", "/pk/compounds"),
    ("POST", "/pk/scenarios"),
    ("PUT", "/pk/scenarios/{sid}"),
    ("DELETE", "/pk/scenarios/{sid}"),
    ("POST", "/pk/scenarios/{sid}/doses"),
    ("PUT", "/pk/scenarios/{sid}/doses/{did}"),
    ("DELETE", "/pk/scenarios/{sid}/doses/{did}"),
})


def test_591_pk_routes_are_exact_browser_witness_candidates_not_clearance():
    # The 591 seven-route witness remains required as 592 adds more PK routes.
    assert PK_ROUTES <= {key for key in gap.EVIDENCE_MODULES if key[1].startswith("/pk/")}
    assert PK_ROUTES <= readiness.BROWSER_WITNESS_CANDIDATES
    report = readiness.report()
    assert not report["missing_witness_source_routes"]
    assert report["global_enable_authorized"] is False
    assert report["strict_csrf_enforce_installed"] is False
    assert report["remaining_unqualified_route_count"] > 0
    plan = gap.build()
    assert plan["strict_csrf_enforcement_change_authorized"] is False
    assert plan["runtime_verified_by_this_report"] is False
    assert len(plan["source_witness_manifest"]) == 37
    actual = { (r["method"], r["path"]) for r in plan["candidate_routes"]}
    assert PK_ROUTES <= actual
    remaining_pk = [r for r in plan["unqualified_routes"]
                    if r["path"].startswith("/pk/")]
    # Release 593 completes source candidates, not runtime or global clearance.
    assert remaining_pk == []


def test_591_real_browser_test_exercises_signed_crud_and_forgery_over_both_schemes():
    source = BROWSER.read_text()
    ast.parse(source)
    marker = "def test_591_pk_scenario_json_lifecycle_signed_and_unsigned_rejected("
    assert source.count(marker) == 1
    lifecycle = source.split(marker, 1)[1]
    assert '@pytest.mark.parametrize("scheme", ("http", "https"))' in source.split(marker, 1)[0][-120:]
    for required in (
        'base = URL if scheme == "http" else HTTPS_URL',
        'window.trackerCsrfToken',
        'page.request.fetch(', 'assert denied.status == 403',
        'await fetch(route, {', 'response.headers.get(\'x-tracker-csrf-report\')',
        'assert result["csrf"] == "valid"',
        'assert pending.value.request.all_headers().get("x-tracker-csrf") == token',
        'unsigned("POST", "/pk/compounds")',
        'unsigned("POST", "/pk/scenarios")',
        'unsigned("PUT", scenario_route)', 'unsigned("DELETE", scenario_route)',
        'unsigned("POST", doses_route)', 'unsigned("PUT", dose_route)',
        'unsigned("DELETE", dose_route)',
        'signed("POST", "/pk/compounds"',
        'signed("POST", "/pk/scenarios"',
        'signed("PUT", scenario_route',
        'signed("POST", doses_route',
        'signed("PUT", dose_route',
        'signed("DELETE", dose_route',
        'signed("DELETE", scenario_route',
        'assert current["doses"] == []',
        'assert all(x["id"] != sid',
    ):
        assert required in lifecycle, required
    assert "TRACKER_TEST_ISOLATED" in source
    assert "TRACKER_TEST_STRICT_CSRF" in source


def test_591_full_chromium_contract_and_runtime_flags_unchanged():
    source = RUNNER.read_text()
    standard, strict = source.split("# Release 521: a second browser gate", 1)
    assert standard.count("tests/browser/test_strict_csrf521.py") == 0
    assert strict.count("tests/browser/test_strict_csrf521.py") == 1
    assert 'TRACKER_CSRF_ENFORCE=1' in strict
    assert source.count('ISOLATED_STRICT_CSRF_BROWSER=PASSED') == 1
    assert source.count('if [[ "$MODE" == full ]]; then') == 4
    assert 'csrf-batch589' in source
    runtime = (ROOT / "app/csrf_enforcement520.py").read_text()
    assert 'os.environ.get("TRACKER_CSRF_ENFORCE", "0") == "1"' in runtime
    script = ROOT / "scripts/tracker_csrf_gap_plan590.py"
    result = subprocess.run([sys.executable, str(script)], cwd=ROOT,
                            text=True, capture_output=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "CSRF_590_GLOBAL_ENFORCEMENT=BLOCKED" in result.stdout


def test_591_unsigned_pk_matrix_matches_all_declared_router_handlers():
    browser_text = BROWSER.read_text()
    source = (ROOT / "app/routers/pk.py").read_text()
    assert "PK_UNSIGNED_ROUTES_591 = (" in browser_text
    between = browser_text.split("PK_UNSIGNED_ROUTES_591 = (", 1)[1].split(
        chr(10) + ")" + chr(10), 1
    )[0]
    cases = re.findall(r'[(]"([A-Z]+)", "(/pk/[^"]+)"[)]', between)
    declared = re.findall(
        r'@router[.](post|put|patch|delete)[(]\s*"([^"]+)"', source
    )
    shape = lambda path: re.sub(r"/[0-9]+(?=/|$)", "/{}", path)
    actual = {(method, shape(path)) for method, path in cases}
    expected = {
        (method.upper(), re.sub(r"[{][^}]+[}]", "{}", "/pk" + path))
        for method, path in declared
    }
    assert len(cases) == len(declared) == 31
    assert len(actual) == len(cases)
    assert actual == expected, (sorted(actual - expected), sorted(expected - actual))
    matrix = browser_text.split(
        "def test_591_pk_unsafe_route_forgery_matrix_negative_only(", 1
    )[1]
    assert 'assert denied.status == 403' in matrix
    assert 'assert "CSRF token required" in denied.text()' in matrix
    assert '("http", "https")' in browser_text
