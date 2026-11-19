"""Release 703: original Vitals/Compound edit controls and mobile-only CSS.

Change-scoped source contracts; no database, HTTP requests or writes.
"""
from pathlib import Path

from jinja2 import Environment

ROOT = Path(__file__).resolve().parents[1]
VITALS = (ROOT / "app/templates/vitals_edit.html").read_text(encoding="utf-8")
COMPOUND = (ROOT / "app/templates/compound_edit.html").read_text(encoding="utf-8")
CSS = (ROOT / "app/static/css/tracker-mobile-edit-actions703.css").read_text(encoding="utf-8")
GUARD = (ROOT / "app/static/js/tracker-vitals-edit-guard.js").read_text(encoding="utf-8")
MOBILE = (ROOT / "app/static/js/tracker-mobile-shell507.js").read_text(encoding="utf-8")
PREVIEW = (ROOT / "scripts/tracker-preview703.sh").read_text(encoding="utf-8")


def test_703_vitals_original_post_cancel_and_unsaved_guard_are_preserved():
    assert VITALS.count('action="/vitals/{{ reading.id }}/edit"') == 1
    assert VITALS.count('method="post"') == 1
    assert VITALS.count('data-tracker-vitals-entry="edit"') == 1
    assert VITALS.count('name="days"') == 1
    assert VITALS.count('name="events"') == 1
    assert VITALS.count('type="submit"') == 1
    assert 'data-vitals-edit-cancel' in VITALS
    assert 'href="/vitals?days={{ days }}&amp;events={{ events }}"' in VITALS
    assert 'class="tracker-mobile-edit-actions703" aria-label="Vitals edit actions"' in VITALS
    assert 'tracker-vitals-edit-guard.js?v=20261103' in VITALS
    assert 'tracker-vitals-entry.js?v=20261103-edit' in VITALS
    assert 'const actions = save.parentElement;' in GUARD
    assert 'actions.append(restore, indicator);' in GUARD
    assert "Discard unsaved changes to this reading?" in GUARD
    assert 'tracker-mobile-edit-actions703.css?v=703' in VITALS
    Environment().parse(VITALS)


def test_703_compound_edit_keeps_unit_lock_and_post_and_single_cancel():
    assert COMPOUND.count('method="post"') == 1
    assert COMPOUND.count('action="/compounds/{{ compound.id }}/edit"') == 1
    assert COMPOUND.count('type="submit"') == 1
    assert COMPOUND.count('<a class="btn" href="/compounds">Cancel</a>') == 1
    assert 'class="ux673-action-row tracker-mobile-edit-actions703"' in COMPOUND
    assert '{% if has_vials %}disabled{% endif %}' in COMPOUND
    assert '{% if has_vials %}<input type="hidden" name="primary_unit"' in COMPOUND
    for name in ("name", "category", "primary_unit", "notes"):
        assert f'name="{name}"' in COMPOUND
    assert 'tracker-mobile-edit-actions703.css?v=703' in COMPOUND
    Environment().parse(COMPOUND)


def test_703_css_preserves_mobile_dock_keyboard_and_dirty_indicators():
    assert '@media screen and (max-width: 760px)' in CSS
    assert 'bottom: calc(4.7rem + env(safe-area-inset-bottom, 0px))' in CSS
    assert 'grid-column: 1 / -1;' in CSS
    assert 'z-index: 29;' in CSS
    assert 'position: sticky;' in CSS
    assert ':root.tracker-mobile-editing' in CSS
    assert 'position: static;' in CSS
    assert '.tracker-vitals-dirty-status' in CSS
    assert 'a[data-vitals-edit-cancel]' in CSS
    assert 'min-height: 48px;' in CSS
    assert ':focus-visible' in CSS
    assert '@media print' in CSS
    assert CSS.count("{") == CSS.count("}")
    assert CSS.count("/*") == CSS.count("*/")
    for forbidden in ("display: none", "visibility: hidden",
                      "pointer-events: none", "position: fixed"):
        assert forbidden not in CSS
    assert 'tracker-mobile-editing' in MOBILE


def test_703_preview_is_fail_closed_and_does_not_install():
    assert 'BASE=5d4c2c44ad5afc7d7a5ce1ae5396a03aa48d1528' in PREVIEW
    assert 'REF=release/703-mobile-edit-form-actions' in PREVIEW
    assert 'git diff --check' in PREVIEW
    assert 'git worktree add --detach' in PREVIEW
    assert 'TRACKER_DATA_DIR="$RUN/test-data"' in PREVIEW
    for path in (
        'app/templates/vitals_edit.html',
        'app/templates/compound_edit.html',
        'app/static/css/tracker-mobile-edit-actions703.css',
        'tests/test_mobile_edit_actions703.py',
        'tests/browser/test_mobile_edit_actions703.py',
    ):
        assert path in PREVIEW
    assert 'RELEASE_703_FORM_BROWSER=PASSED' in PREVIEW
    assert 'RELEASE_703_PREVIEW=PASSED_ISOLATED_NO_INSTALL' in PREVIEW
