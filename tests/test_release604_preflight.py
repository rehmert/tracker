"""Release 604 read-only release impact gate and navigation contracts."""
from __future__ import annotations

import importlib.util
import subprocess
from pathlib import Path

import pytest
from app.templating import templates

ROOT = Path(__file__).resolve().parents[1]
BASE_603 = "ca746febdc037676ca9af9b08fa5cc5ac52a4cfc"

spec = importlib.util.spec_from_file_location(
    "tracker_impact_604", ROOT / "scripts/tracker-impact-preflight604.py"
)
impact = importlib.util.module_from_spec(spec)
spec.loader.exec_module(impact)


def source(path):
    return (ROOT / path).read_text(encoding="utf-8")


def run_git(repo, *args):
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True, text=True, check=True,
    )
    return result.stdout.strip()


def repo_fixture(tmp_path, *, test_source):
    root = tmp_path / "fixture"
    (root / "app/templates").mkdir(parents=True)
    (root / "app/static/js").mkdir(parents=True)
    (root / "tests").mkdir()
    (root / "app/templates/demo.html").write_text(
        '<script src="/static/js/demo.js?v=1" defer></script>\n'
    )
    (root / "app/static/js/demo.js").write_text("window.demo = 1;\n")
    (root / "tests/test_old.py").write_text(test_source)
    run_git(root, "init", "-q")
    run_git(root, "config", "user.name", "Tracker Tests")
    run_git(root, "config", "user.email", "tests@example.invalid")
    run_git(root, "add", "-A")
    run_git(root, "commit", "-qm", "base")
    return root, run_git(root, "rev-parse", "HEAD")


def bump(root, *, change_asset=True, change_url=True, change_test=None):
    if change_asset:
        (root / "app/static/js/demo.js").write_text("window.demo = 2;\n")
    if change_url:
        p = root / "app/templates/demo.html"
        p.write_text(p.read_text().replace("demo.js?v=1", "demo.js?v=2"))
    if change_test is not None:
        (root / "tests/test_old.py").write_text(change_test)
    run_git(root, "add", "-A")
    run_git(root, "commit", "-qm", "update")
    return run_git(root, "rev-parse", "HEAD")


def test_604_detects_legacy_assertion_before_full_suite(tmp_path):
    root, base = repo_fixture(
        tmp_path,
        test_source='def test_old():\n    assert "demo.js?v=1" in "html"\n',
    )
    target = bump(root)
    errors = impact.check(root, base, target)
    assert any("tests/test_old.py" in item for item in errors), errors


def test_604_detects_legacy_marker_loop_before_full_suite(tmp_path):
    root, base = repo_fixture(
        tmp_path,
        test_source=(
            "def test_old():\n"
            "    for marker in ('demo.js?v=1', 'keep'):\n"
            "        assert marker in 'html'\n"
        ),
    )
    errors = impact.check(root, base, bump(root))
    assert any("tests/test_old.py" in item for item in errors), errors


def test_604_allows_updated_legacy_assertions(tmp_path):
    root, base = repo_fixture(
        tmp_path,
        test_source='def test_old():\n    assert "demo.js?v=1" in "html"\n',
    )
    target = bump(
        root,
        change_test='def test_old():\n    assert "demo.js?v=2" in "html"\n',
    )
    assert impact.check(root, base, target) == []


def test_604_rejects_unbumped_modified_asset(tmp_path):
    root, base = repo_fixture(
        tmp_path, test_source="def test_old():\n    pass\n",
    )
    target = bump(root, change_url=False)
    errors = impact.check(root, base, target)
    assert any("unchanged asset URL" in item for item in errors), errors


def test_604_ignores_negative_historical_examples(tmp_path):
    root, base = repo_fixture(
        tmp_path,
        test_source=(
            "def test_negative():\n"
            "    obsolete = 'demo.js?v=1'\n"
            "    assert obsolete not in 'current'\n"
        ),
    )
    assert impact.check(root, base, bump(root)) == []


def test_604_vial_workflows_all_have_one_toolbar():
    html = source("app/templates/vials.html")
    start = html.index('<h1>Vials</h1>')
    end = html.index('<form method="get"', start)
    top = html[start:end]
    assert top.count('<nav class="tracker-vial-jumps603"') == 1
    assert '<nav class="ux-shortcuts">' not in top
    assert 'aria-label="Vials actions and sections"' in top
    for route in (
        "#tracker-vials-sortable", "#tracker-vial-find-panel",
        "#bulk-selection-toolbar", "#tracker-inventory-reports",
        "#tracker-vial-lifecycle", "/purchases#new-purchase",
        "/inventory-intelligence", "/inventory-alerts", "/reconciliation",
    ):
        assert top.count(f'href="{route}"') == 1, route
    templates.env.get_template("vials.html")


def test_604_quick_shortcuts_still_have_exact_original_destinations():
    html = source("app/templates/quick_entry.html")
    fast = html.split('<nav class="tracker-quick-fast-paths"', 1)[1].split(
        "</nav>", 1
    )[0]
    expected = (
        "/mobile", "/food#food-quick-log", "/food#food-water",
        "/health-insights", "/replenishment-review",
        "/mobile#mobile-quick-vitals", "/doses#quick-dose-entry",
        "/vitals#quick-vitals-entry", "/vitals#quick-vitals-weight",
        "/vitals#quick-vitals-bp", "/vitals#quick-vitals-pulse",
        "/supplies#tracker-stock-section", "/purchases#new-purchase",
        "/labs/new#lab-manual-entry", "/labs/new#lab-csv-entry",
    )
    assert sum(fast.count(f'href="{route}"') for route in expected) == 15
    assert all(fast.count(f'href="{route}"') == 1 for route in expected)
    assert fast.count('<details class="tracker-quick-fast-more604">') == 1
    assert 'More direct shortcuts</summary>' in fast
    assert fast.count('<a href=') == 15
    assert html.count('data-quick-daily') == 5
    assert "tracker-quick-entry.js?v=603" in html
    assert "tracker-navigation604.css?v=604b" in html
    assert "<form" not in html
    templates.env.get_template("quick_entry.html")


def test_604_release_gate_runs_before_expensive_qualification():
    script = source("scripts/tracker-release.sh")
    assert script.count("tracker-impact-preflight604.py") == 1
    assert script.index("tracker-impact-preflight604.py") < script.index(
        "ISOLATED BROWSER QUALIFICATION"
    )
    assert script.index("tracker-impact-preflight604.py") < script.index(
        "COMPLETE REGRESSION SUITE"
    )
    assert "timeout 180" in script
    assert "=== RELEASE 604 FOCUSED REGRESSION BEFORE FULL BROWSER ===" in script
    assert script.index("RELEASE 604 FOCUSED REGRESSION BEFORE FULL BROWSER") < (
        script.index("ISOLATED BROWSER QUALIFICATION")
    )
    assert "tests/test_release604_navigation_browser.py" in script
    assert "tests/test_release604_preflight.py" in script
    assert "timeout 600 bash" in script
    assert 'bash "$QA/scripts/tracker-browser-qualify.sh"' in script
    assert "timeout 1200" in script
    assert "verify_prod_approval" in script
    # No deploy/test bypass switches were introduced.
    assert "git diff --check" in script


def test_604_current_worktree_has_clean_asset_contracts():
    head = run_git(ROOT, "rev-parse", "HEAD")
    if head == BASE_603:
        pytest.skip("Running against installed Release 603, not the candidate")
    assert impact.check(ROOT, BASE_603, head) == []


def test_604_primary_shortcuts_preserve_release602_mobile_scrolling():
    """Protect the 602 phone overflow contract after changing the DOM nesting."""
    css = source("app/static/css/tracker-navigation604.css")
    original = source("app/static/css/tracker-mobile-daily602.css")
    html = source("app/templates/quick_entry.html")
    strict = source("tests/browser/test_strict_csrf521.py")
    fixture = source("tests/test_release604_navigation_browser.py")

    assert 'tracker-navigation604.css?v=604b' in html
    assert ".tracker-quick-fast-paths {" in original
    assert "overflow-x: auto;" in original
    assert ".tracker-quick-fast-primary604 {" in css
    assert "flex-wrap: nowrap;" in css
    assert "overflow-x: auto;" in css
    assert "overscroll-behavior-x: contain;" in css
    assert ".tracker-quick-fast-paths {" in css
    assert "overflow: visible;" in css
    assert "tracker-mobile-daily602.css" in fixture
    assert "el.scrollWidth > el.clientWidth" in fixture
    assert "test_602_food_and_quick_entry_phone_density" in strict
    assert "links.scrollWidth > links.clientWidth" in strict
    assert "getComputedStyle(links).overflowX === 'auto'" in strict
    assert "gridTemplateColumns.split(' ').length === 2" in strict
