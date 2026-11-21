"""Release 702: one Saved Food edit Save/Cancel form and mobile-only styling.

No application data or server calls; existing Release 669 tests cover writes.
"""
from pathlib import Path
from html.parser import HTMLParser

from jinja2 import Environment

ROOT = Path(__file__).resolve().parents[1]
EDITOR = (ROOT / "app/templates/food_saved_edit669.html").read_text(encoding="utf-8")
CSS = (ROOT / "app/static/css/tracker-saved-food-actions702.css").read_text(encoding="utf-8")
BASE = (ROOT / "app/templates/base.html").read_text(encoding="utf-8")
MOBILE_JS = (ROOT / "app/static/js/tracker-mobile-shell507.js").read_text(encoding="utf-8")
PREVIEW = (ROOT / "scripts/tracker-preview702.sh").read_text(encoding="utf-8")


class EditorControls(HTMLParser):
    def __init__(self):
        super().__init__()
        self.controls = []
        self.forms = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "form":
            self.forms.append(attrs)
        if tag == "button" and attrs.get("type") == "submit":
            self.controls.append(("save", attrs))
        if tag == "a" and ("tracker-food-editor-back702" in attrs.get("class", "")
                           or attrs.get("class") == "btn"):
            self.controls.append(("link", attrs))


def test_702_exact_original_actions_without_duplicate_forms_or_post_changes():
    parser = EditorControls()
    parser.feed(EDITOR)
    # Release 739 introduces an independent, guarded Delete form; the
    # original edit form remains first, unchanged and non-nested.
    assert len(parser.forms) == 2
    assert parser.forms[0]["method"] == "post"
    assert parser.forms[0]["action"] == "/food/saved/{{ product.id }}/edit"
    assert parser.forms[1]["method"] == "post"
    assert parser.forms[1]["action"] == "/food/saved/{{ product.id }}/delete"
    submit_controls = [x[1] for x in parser.controls if x[0] == "save"]
    assert len(submit_controls) == 2
    assert any(x.get("form") == "food739-delete-{{ product.id }}" for x in submit_controls)
    assert len([x for x in parser.controls if x[0] == "link"]) == 2
    assert EDITOR.count('class="ux673-action-row tracker-food-editor-actions702"') == 1
    assert EDITOR.count('class="tracker-food-editor-back702"') == 1
    assert EDITOR.count("Save Food Changes") == 1
    assert EDITOR.count(">Cancel</a>") == 1
    assert EDITOR.count('href="/food?day={{ day }}#food-search"') == 2
    assert 'name="version" value="{{ version }}"' in EDITOR
    assert 'name="day" value="{{ day }}"' in EDITOR
    assert 'name="confirm_history"' not in EDITOR
    Environment().parse(EDITOR)


def test_702_css_is_mobile_and_keyboard_scoped_without_hidden_controls():
    assert 'tracker-saved-food-actions702.css?v=702' in EDITOR
    assert '@media screen and (max-width: 760px)' in CSS
    assert ':root.tracker-mobile-editing' in CSS
    assert 'position: sticky;' in CSS
    assert 'position: static;' in CSS
    assert 'bottom: calc(4.7rem + env(safe-area-inset-bottom, 0px))' in CSS
    assert 'z-index: 29' in CSS
    assert 'min-height: 44px' in CSS
    assert 'min-height: 48px' in CSS
    assert ':focus-visible' in CSS
    assert '@media print' in CSS
    for disallowed in ('display: none', 'visibility: hidden', 'pointer-events: none',
                       'position: fixed', '@media (min-width: 761px)'):
        assert disallowed not in CSS
    assert 'tracker-mobile-editing' in MOBILE_JS
    assert 'tracker-mobile-shell507.js?v=603' in BASE


def test_702_preview_is_pinned_disposable_and_change_scoped():
    assert 'BASE=afba8b1f810d777927679cb6feaaa043396f805d' in PREVIEW
    assert 'REF=release/702-saved-food-mobile-actions' in PREVIEW
    assert 'git diff --check' in PREVIEW
    for path in (
        'app/templates/food_saved_edit669.html',
        'app/static/css/tracker-saved-food-actions702.css',
        'tests/test_saved_food_mobile_actions702.py',
        'tests/browser/test_saved_food_mobile_actions702.py',
    ):
        assert path in PREVIEW
    assert 'TRACKER_DATA_DIR="$RUN/test-data"' in PREVIEW
    assert 'scripts/tracker-release-scoped702.sh' in PREVIEW
    assert 'RELEASE_702_FORM_BROWSER=PASSED' in PREVIEW
    assert 'RELEASE_702_PREVIEW=PASSED_ISOLATED_NO_INSTALL' in PREVIEW
    assert 'git worktree add --detach' in PREVIEW
