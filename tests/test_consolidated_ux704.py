"""Release 704 consolidated UX: source, safety, and read-only inventory contracts."""
import importlib.util
from pathlib import Path
import re

from jinja2 import Environment

ROOT = Path(__file__).resolve().parents[1]
T = ROOT / "app/templates"
C = ROOT / "app/static/css/tracker-edit-actions704.css"
J = ROOT / "app/static/js/tracker-edit-feedback704.js"
FILES = (
    "dose_edit.html", "page_edit.html", "workout_backfill658.html",
    "preparation_edit.html", "lab_form.html",
)


def src(name):
    return (T / name).read_text(encoding="utf-8")


def test_704_single_original_action_group_in_each_long_editor():
    env = Environment(extensions=["jinja2.ext.do"])
    for name in FILES:
        html = src(name)
        env.parse(html)
        assert html.count("tracker-edit-actions704\"") == 1, name
        assert html.count('class="tracker-edit-feedback704"') == 1, name
        assert html.count('role="alert" hidden') == 1, name
        assert html.count('tracker-edit-actions704.css?v=704') == 1, name
        assert html.count('tracker-edit-feedback704.js?v=704') == 1, name
        assert 'Cancel' in html, name
    assert src("dose_edit.html").count('action="/doses/{{ dose.id }}/edit"') == 1
    assert src("page_edit.html").count('form method="post"') == 1
    assert src("workout_backfill658.html").count('id="workout658-save"') == 1
    assert src("preparation_edit.html").count('Save correction</button>') == 1
    assert src("lab_form.html").count('data-lab-manual-entry') == 1


def test_704_existing_safety_workflows_are_not_replaced():
    dose=src("dose_edit.html")
    for marker in (
        'name="supply_id_used"', 'name="supply_qty_{{ s.id }}"',
        'id="tracker-dose-correction-review"', "Change history",
        'tracker-dose-correction-review.js',
    ):
        assert marker in dose
    notes=src("page_edit.html")
    for marker in (
        'id="notes-discard-draft"', 'id="notes-body"',
        'notes_draft_recovery.js', 'hx-post="/pages/preview"',
        'id="notes-visual"', 'id="notes-source-mode"',
    ):
        assert marker in notes
    workout=src("workout_backfill658.html")
    for marker in (
        'action="/workouts/backfill/import.csv"',
        'action="/workouts/backfill"', 'id="workout658-rows"',
        'id="workout658-save"', 'id="workout658-add"',
        'class="workout658-save-actions tracker-edit-actions704"',
    ):
        assert marker in workout
    prep=src("preparation_edit.html")
    assert 'name="supply_qty_{{ s.id }}"' in prep
    assert 'name="supply_id_used"' in prep
    assert 'href="/vials/{{ vial.id }}"' in prep
    lab=src("lab_form.html")
    for marker in (
        'data-lab-csv-entry', 'data-lab-manual-entry',
        'action="/labs/import-csv"', 'action="/labs"',
        'data-lab-entry-review', 'data-lab-duplicate-warning',
        'id="lab-rows"', 'hx-get="/labs/row"',
        'tracker-lab-entry-safeguards.js',
    ):
        assert marker in lab
    assert lab.count("Save report</button>") == 1


def test_704_shared_css_mobile_only_and_keyboard_safe():
    css=C.read_text(encoding="utf-8")
    assert '@media screen and (max-width: 760px)' in css
    assert 'bottom: calc(4.7rem + env(safe-area-inset-bottom, 0px))' in css
    assert 'grid-column: 1 / -1;' in css
    assert 'position: sticky;' in css
    assert ':root.tracker-mobile-editing' in css
    assert 'z-index: 29;' in css
    assert 'min-height: 48px;' in css
    assert ':focus-visible' in css
    assert '#notes-discard-draft' in css
    assert '@media print' in css
    assert css.count("{") == css.count("}")
    assert css.count("/*") == css.count("*/")
    for forbidden in ("display: none", "visibility: hidden",
                      "pointer-events: none", "position: fixed"):
        assert forbidden not in css


def test_704_feedback_only_reports_browser_invalid_without_writes():
    js=J.read_text(encoding="utf-8")
    for token in (
        "form.addEventListener('invalid'", "form.addEventListener('input'",
        "form.addEventListener('change'", "feedback.hidden = false",
        "feedback.hidden = true", "control.validity.valid",
        "role", # role is owned by template, not JS; only commentary may mention
    ):
        if token != "role":
            assert token in js, token
    for forbidden in (
        "fetch(", "XMLHttpRequest", "localStorage", "sessionStorage",
        "requestSubmit(", ".submit(", "preventDefault(", ".value =",
        "FormData(", "document.cookie",
    ):
        assert forbidden not in js, forbidden


def test_704_repository_audit_is_read_only_and_issue_status_is_honest():
    spec=importlib.util.spec_from_file_location(
        "audit704",ROOT / "scripts/tracker-ux-audit704.py"
    )
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    report=module.report()
    assert report["template_count"] >= 50
    assert report["post_form_count"] >= 10
    assert set(report["updated_editors"]) == set(FILES)
    assert set(report["existing_editor_coverage"]) == {
        "food_saved_edit669.html","vitals_edit.html","compound_edit.html"
    }
    assert any("still required" in note for note in report["notes"])
    assert (ROOT/"docs/dependencies/observed-2026-11-11-py313.json").exists()
    assert (ROOT/"docs/dependencies/candidate-constraints-py313.txt").exists()
    assert (ROOT/"scripts/tracker_dependency_baseline569.py").exists()
    assert (ROOT/"scripts/tracker_csrf_review_queue623.py").exists()


def test_704_latency_audit_refuses_non_loopback():
    spec=importlib.util.spec_from_file_location(
        "latency704", ROOT / "scripts/tracker-latency704.py"
    )
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    for url in (
        "https://127.0.0.1:8000", "http://localhost:8000",
        "http://tracker-prod:8000", "http://127.0.0.1:8000/food",
        "http://127.0.0.1:8000?q=a", "http://user:pass@127.0.0.1:8000",
    ):
        try:
            module.run(url)
        except ValueError:
            pass
        else:
            raise AssertionError(f"Expected URL rejection: {url}")
    assert module.PAGES == (
        "/", "/mobile", "/food", "/doses", "/vitals", "/workouts/quick",
        "/vials", "/purchases", "/coas", "/labs",
    )


def test_704_isolated_preview_is_fail_closed():
    preview=(ROOT/"scripts/tracker-preview704.sh").read_text(encoding="utf-8")
    assert 'BASE=17e7a68daf8cb9a0c6219b162a54b9e7a1b9f8e2' in preview
    assert 'REF=release/704-consolidated-ux-quality' in preview
    assert 'git diff --check' in preview
    assert 'git worktree add --detach' in preview
    assert 'TRACKER_DATA_DIR="$CANDIDATE_DATA"' in preview
    assert 'scripts/tracker-release-scoped704.sh' in preview
    assert 'RELEASE_704_CONSOLIDATED_BROWSER=PASSED' in preview
    assert 'RELEASE_704_PREVIEW=PASSED_ISOLATED_NO_INSTALL' in preview
