"""Release 704: consolidated untouched write contracts plus mobile presentation.

This is source-only: legacy validation, draft recovery, lab safeguards,
and recorded-workout semantics remain the responsibility of existing tests.
"""
from pathlib import Path
from jinja2 import Environment

ROOT = Path(__file__).resolve().parents[1]
T = ROOT / "app/templates"
CSS = (ROOT / "app/static/css/tracker-consolidated-forms704.css").read_text(encoding="utf-8")
NOTES = (T / "page_edit.html").read_text(encoding="utf-8")
WORKOUT = (T / "workout_backfill658.html").read_text(encoding="utf-8")
LAB = (T / "lab_form.html").read_text(encoding="utf-8")
LAB_GATE = (ROOT / "app/static/js/tracker-lab-sticky-actions704.js").read_text(encoding="utf-8")
PREVIEW = (ROOT / "scripts/tracker-preview704.sh").read_text(encoding="utf-8")


def test_704_only_original_note_actions_and_recovery_unchanged():
    assert NOTES.count("tracker-consolidated-forms704.css?v=704") == 1
    assert NOTES.count('class="row tracker-form-actions704 tracker-form-actions704--notes"') == 1
    assert NOTES.count('action="{{ \'/pages/\' ~ p.id if p else \'/pages\' }}"') == 1
    assert NOTES.count('class="primary">Save page</button>') == 1
    assert NOTES.count('id="notes-discard-draft"') == 1
    assert NOTES.count('class="btn" href="{{ \'/pages/\' ~ p.id if p else \'/pages\' }}">Cancel</a>') == 1
    assert 'notes_draft_recovery.js' in NOTES
    assert 'hx-post="/pages/preview"' in NOTES
    assert 'id="notes-visual"' in NOTES
    Environment().parse(NOTES)


def test_704_only_original_workout_actions_and_actual_set_protection():
    assert WORKOUT.count("tracker-consolidated-forms704.css?v=704") == 1
    assert WORKOUT.count('class="workout658-save-actions tracker-form-actions704 tracker-form-actions704--workout"') == 1
    assert WORKOUT.count('id="workout658-form"') == 1
    assert WORKOUT.count('id="workout658-save"') == 1
    assert WORKOUT.count('action="/workouts/backfill"') == 1
    assert WORKOUT.count('action="/workouts/backfill/import.csv"') == 1
    assert WORKOUT.count('<a class="btn" href="/workouts">Cancel</a>') == 1
    assert 'data-max-rows="{{ max_rows }}"' in WORKOUT
    assert 'name="set_time"' in WORKOUT
    assert 'workout658-error" role="alert"' in WORKOUT
    Environment().parse(WORKOUT)


def test_704_only_manual_lab_actions_csv_and_dynamic_add_untouched():
    assert LAB.count("tracker-consolidated-forms704.css?v=704") == 1
    assert LAB.count("tracker-lab-sticky-actions704.js?v=704") == 1
    assert LAB.count('class="row tracker-form-actions704 tracker-form-actions704--lab"') == 1
    assert LAB.count('action="/labs/import-csv"') == 1
    assert LAB.count('action="/labs"') == 1
    assert LAB.count('data-lab-manual-entry') == 1
    assert LAB.count('data-lab-csv-entry') == 1
    assert LAB.count('hx-get="/labs/row"') == 1
    assert LAB.count('hx-target="#lab-rows"') == 1
    assert LAB.count('<button class="primary">Save report</button>') == 1
    assert LAB.count('<a class="btn" href="/labs">Cancel</a>') == 1
    for asset in ("tracker-lab-entry-safeguards.js",
                  "tracker-lab-navigation.js", "tracker-lab-entry-review.js"):
        assert asset in LAB
    Environment().parse(LAB)


def test_704_css_is_keyboard_safe_and_scoped_to_three_editor_action_rows():
    assert '@media screen and (max-width: 760px)' in CSS
    assert '@media print' in CSS
    assert 'position: sticky;' in CSS
    assert 'bottom: calc(4.7rem + env(safe-area-inset-bottom, 0px))' in CSS
    assert 'z-index: 29' in CSS
    assert 'min-height: 48px' in CSS
    assert ':root.tracker-mobile-editing' in CSS
    assert ':focus-visible' in CSS
    assert CSS.count("{") == CSS.count("}")
    assert CSS.count("/*") == CSS.count("*/")
    for forbidden in ("display: none", "visibility: hidden", "position: fixed",
                      "pointer-events: none", "!important; } /* disable"):
        assert forbidden not in CSS
    assert 'tracker-form-actions704--lab' in CSS
    assert 'grid-template-columns: repeat(3, minmax(0, 1fr));' in CSS
    assert 'form.tracker-lab-actions704-active' in CSS
    assert 'position: static;' in CSS
    # A 320px form that begins near the dock cannot push a sticky bar
    # above the containing form's top; enforce compact chrome, not
    # smaller touch targets or relaxed overlap checks.
    assert 'margin-top: 0;' in CSS
    assert 'gap: .25rem;' in CSS
    assert 'padding: .35rem;' in CSS
    assert 'padding: .25rem .12rem;' in CSS
    assert 'line-height: 1.2;' in CSS
    assert 'tracker-form-actions704--notes' in CSS
    for token in (
        'form[data-lab-manual-entry]',
        'tracker-form-actions704--lab',
        'tracker-mobile-editing',
        'getBoundingClientRect()',
        'formTop + barHeight + 16 <= dockTop',
        'window.addEventListener("scroll", schedule, { passive: true })',
        'requestAnimationFrame(refresh)',
        'MutationObserver(schedule)',
        'tracker-lab-actions704-active',
    ):
        assert token in LAB_GATE
    for forbidden in (
        'fetch(', 'XMLHttpRequest', 'localStorage', 'sessionStorage',
        'requestSubmit(', '.submit(', 'form.action', 'window.location=',
    ):
        assert forbidden not in LAB_GATE


def test_704_preview_guards_scope_and_disposable_data():
    assert 'BASE=17e7a68daf8cb9a0c6219b162a54b9e7a1b9f8e2' in PREVIEW
    assert 'REF=release/704-consolidated-ux-hardening' in PREVIEW
    assert 'git diff --check' in PREVIEW
    assert 'git worktree add --detach' in PREVIEW
    assert 'TRACKER_DATA_DIR="$CANDIDATE_DATA"' in PREVIEW
    assert 'RELEASE_704_PREVIEW=PASSED_ISOLATED_NO_INSTALL' in PREVIEW
    for path in ("app/templates/page_edit.html", "app/templates/workout_backfill658.html",
                 "app/templates/lab_form.html",
                 "app/static/css/tracker-consolidated-forms704.css",
                 "app/static/js/tracker-lab-sticky-actions704.js",
                 "tests/browser/test_consolidated_forms704.py"):
        assert path in PREVIEW
