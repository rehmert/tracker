"""Release 700: narrow shared toolbar and Daily Shortcuts CSS contracts.

Actual pixel and computed-style equivalence is separately checked by
isolated two-worktree Chromium at compact/balanced/comfortable densities.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = (ROOT / "app/templates/base.html").read_text(encoding="utf-8")
CSS687 = (ROOT / "app/static/css/tracker-shortcuts-toolbar687.css").read_text(encoding="utf-8")
CSS688 = (ROOT / "app/static/css/tracker-dashboard-polish688.css").read_text(encoding="utf-8")
PREVIEW = (ROOT / "scripts/tracker-preview700.sh").read_text(encoding="utf-8")
PARITY = (ROOT / "tests/browser/test_css_parity700.py").read_text(encoding="utf-8")


def test_700_shared_search_sizing_is_deduplicated_at_both_breakpoints():
    selector = (
        "#main-content > .workspace-toolbar > "
        ":is(.workspace-search,.workspace-nav-find)"
    )
    assert CSS687.count(selector) == 2
    assert "flex: 1 1 9rem;" in CSS687
    assert "min-width: 7rem;" in CSS687
    assert "flex: 1 1 12rem;" in CSS687
    assert "min-width: 9rem;" in CSS687
    assert "@media (min-width: 761px)" in CSS687
    assert "@media (min-width: 761px) and (max-width: 1199px)" in CSS687
    # The mobile order, tap-target and visibility rules still exist.
    assert ".tracker-account-action687 {\n    order: -4;\n    min-height: 44px;" in CSS687
    assert "display: none !important" in CSS687


def test_700_compact_daily_alignment_must_override_687_specificity():
    # 687 sets compact links to flex-start with a :root[data-density]
    # selector; the later 688 rule must explicitly re-center them.
    base_selector = "#main-content nav.tracker-daily-flow559-links > a {"
    compact_selector = (
        ':root[data-density="compact"] '
        '#main-content nav.tracker-daily-flow559-links > a {'
    )
    base_rules = CSS688.split(base_selector, 1)[1].split("}", 1)[0]
    compact_rules = CSS688.split(compact_selector, 1)[1].split("}", 1)[0]
    assert "align-items: flex-start;" in CSS687
    assert "justify-content: center;" in CSS687
    for expected in ("display: flex;", "align-items: center;",
                     "justify-content: center;", "min-height: 48px;"):
        assert expected in base_rules
    for expected in ("min-height: 44px;", "padding: .18rem .38rem;",
                     "align-items: center;", "justify-content: center;"):
        assert expected in compact_rules
    assert "display: none" not in CSS688
    assert "font-size: 0" not in CSS688


def test_700_asset_cache_refresh_and_original_component_order():
    assert BASE.count("/static/css/tracker-shortcuts-toolbar687.css?v=687-css700") == 1
    assert BASE.count("/static/css/tracker-dashboard-polish688.css?v=688") == 1
    assert BASE.index("tracker-compact-aggressive686.css?v=686") < BASE.index(
        "tracker-shortcuts-toolbar687.css?v=687-css700"
    )
    assert BASE.index("tracker-shortcuts-toolbar687.css?v=687-css700") < BASE.index(
        "tracker-dashboard-polish688.css?v=688"
    )
    assert BASE.index("tracker-dashboard-polish688.css?v=688") < BASE.index(
        "tracker-workout-footnote689.css?v=689"
    )


def test_700_preview_is_pinned_scoped_private_and_runs_both_visual_gates():
    assert "BASE=a49cee23a1c3b87312a603a169be070fbe93faee" in PREVIEW
    assert "REF=release/700-shared-toolbar-css" in PREVIEW
    assert 'TRACKER_700_BASE_SOURCE="$BASE_QA"' in PREVIEW
    assert 'TRACKER_700_CANDIDATE_SOURCE="$CANDIDATE_QA"' in PREVIEW
    assert 'TRACKER_DATA_DIR="$BASE_DATA"' in PREVIEW
    assert 'TRACKER_DATA_DIR="$CANDIDATE_DATA"' in PREVIEW
    assert "tests/browser/test_css_parity700.py" in PREVIEW
    assert 'TRACKER_700_PARITY_ARTIFACT_DIR="$ARTIFACTS"' in PREVIEW
    assert "context.route(\"**/*\", lambda route: route.abort())" in PARITY
    assert "Baseline screenshot not deterministic" in PARITY
    assert "page = context.new_page()" in PARITY
    assert "ref_page, candidate_page" not in PARITY
    assert "STABLE_STYLE" in PARITY
    assert "save_private_diff" in PARITY
    assert "scripts/tracker_visual_regression698.py" in PREVIEW
    assert "RELEASE_700_PREVIEW=PASSED_ISOLATED_NO_INSTALL" in PREVIEW
    assert "git worktree add --detach" in PREVIEW
    assert "git diff --check" in PREVIEW
    assert 'rm -rf -- "$RUN"' in PREVIEW
