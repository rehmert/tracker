"""Release 699: source contracts for the first CSS consolidation increment.

Only the Release 685/686 density stylesheets may change. Earlier computed
behavior is independently tested in the original 685 and 686 test modules.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CSS685 = (ROOT / "app/static/css/tracker-layout-density685.css").read_text(encoding="utf-8")
CSS686 = (ROOT / "app/static/css/tracker-compact-aggressive686.css").read_text(encoding="utf-8")
BASE = (ROOT / "app/templates/base.html").read_text(encoding="utf-8")
PREVIEW = (ROOT / "scripts/tracker-preview699.sh").read_text(encoding="utf-8")


def test_699_factor_shared_685_rules_without_altering_density_values():
    for selector in (
        ":root[data-density=\"compact\"] #main-content :is(.dashboard-hero,.page-header)",
        ":root[data-density=\"compact\"] #main-content :is(.dashboard-hero,.page-header) .eyebrow",
        ":root[data-density=\"compact\"] #main-content :is(.dashboard-hero,.page-header) h1",
        ":root[data-density=\"compact\"] #main-content :is(.section-intro,.panel-heading) > :is(h2,h3)",
        ":root[data-density=\"balanced\"] #main-content :is(.dashboard-panel,.tracker-ui-card,.ux673-card)",
        ".dashboard-panel,.insight-card,.inventory-card,.today-card,.protocol-card",
    ):
        assert selector in CSS685
    # Previously the same compact card padding was applied twice in 685.
    assert CSS685.count("padding: var(--tracker685-pad-y) var(--tracker685-pad-x);") == 2
    assert CSS685.count("--tracker685-pad-y:") == 2
    assert CSS685.count("--tracker685-pad-x:") == 2
    assert "display: none" not in CSS685
    assert "font-size:" not in CSS685


def test_699_mobile_action_contract_preserved_by_685_and_686():
    # The original 685 mobile rule still includes these same 44px controls.
    for selector in (
        ".tracker-ui-action",
        ".ux673-action-row > a",
        ".ux673-action-row > button",
    ):
        assert selector in CSS685
    assert "min-height: 44px" in CSS685
    # The later 686 mobile override only adds the Daily-specific actions.
    for selector in (
        ".tracker-daily-actions a",
        ".tracker-daily-mode button",
        ".tracker-daily-list li a",
    ):
        assert selector in CSS686
    assert "min-height: 44px" in CSS686
    assert "display: none" not in CSS686
    assert "font-size:" not in CSS686


def test_699_loaded_css_order_and_noncompact_modes_unchanged():
    assert BASE.count('tracker-layout-density685.css?v=685') == 1
    assert BASE.count('tracker-compact-aggressive686.css?v=686') == 1
    assert BASE.index('tracker-layout-density685.css?v=685') < BASE.index(
        'tracker-compact-aggressive686.css?v=686'
    )
    assert 'data-density="balanced"' in CSS685
    assert 'data-density="comfortable"' not in CSS686


def test_699_preview_is_scoped_to_two_css_files_and_disposable_comparison():
    assert 'BASE=a280455fe031c8aa634b84128bab81569d075779' in PREVIEW
    assert 'REF=release/699-css-consolidation' in PREVIEW
    assert 'TRACKER_699_BASE_CSS="$BASE_QA/app/static/css"' in PREVIEW
    assert 'TRACKER_699_CANDIDATE_CSS="$CANDIDATE_QA/app/static/css"' in PREVIEW
    assert 'TRACKER_DATA_DIR="$BASE_DATA"' in PREVIEW
    assert 'TRACKER_DATA_DIR="$CANDIDATE_DATA"' in PREVIEW
    assert 'tests/browser/test_css_parity699.py' in PREVIEW
    assert "scripts/tracker_visual_regression698.py" in PREVIEW
    assert "RELEASE_699_PREVIEW=PASSED_ISOLATED_NO_INSTALL" in PREVIEW
    assert 'git worktree add --detach' in PREVIEW
    assert 'git diff --check' in PREVIEW
    assert 'rm -rf -- "$RUN"' in PREVIEW
