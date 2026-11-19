"""Release 701: mobile Log sheet links and unchanged recording form contracts.

Source only; no DB connection, application login or POST.
"""
from html.parser import HTMLParser
from pathlib import Path

from jinja2 import Environment

ROOT = Path(__file__).resolve().parents[1]
SHEET = (ROOT / "app/templates/_mobile_quick528.html").read_text(encoding="utf-8")
TODAY = (ROOT / "app/templates/mobile_today509.html").read_text(encoding="utf-8")
QUICK = (ROOT / "app/templates/quick_entry.html").read_text(encoding="utf-8")
BASE = (ROOT / "app/templates/base.html").read_text(encoding="utf-8")
JS = (ROOT / "app/static/js/tracker-mobile-quick528.js").read_text(encoding="utf-8")
CSS = (ROOT / "app/static/css/tracker-mobile-quick528.css").read_text(encoding="utf-8")
PREVIEW = (ROOT / "scripts/tracker-preview701.sh").read_text(encoding="utf-8")

EXPECTED_LINKS = (
    ("/food#food-quick-log", "Food"),
    ("/doses#quick-dose-entry", "Dose"),
    ("/labs/new#lab-manual-entry", "Labs"),
    ("/workouts/quick", "Log Workout Set"),
    ("/regimen#reg635-today", "Log Supplements / Meds"),
    ("/quick-entry", "All actions"),
)


class ChoiceLinks(HTMLParser):
    def __init__(self):
        super().__init__()
        self.active = False
        self.anchors = []
        self.buttons = []
        self.current = None

    def handle_starttag(self, tag, pairs):
        attrs = dict(pairs)
        if tag == "div" and "data-quick528-choices" in attrs:
            self.active = True
        elif self.active and tag == "a":
            self.current = [attrs["href"], ""]
        elif self.active and tag == "button":
            self.buttons.append(attrs.get("data-quick528-choice"))

    def handle_data(self, data):
        if self.current is not None:
            self.current[1] += data

    def handle_endtag(self, tag):
        if tag == "a" and self.current is not None:
            self.anchors.append(tuple(map(str.strip, self.current)))
            self.current = None
        if tag == "div" and self.active:
            self.active = False


def test_701_mobile_sheet_adds_existing_direct_paths_in_correct_order():
    parser = ChoiceLinks()
    parser.feed(SHEET)
    assert parser.buttons == ["weight", "bp", "water"]
    assert tuple(parser.anchors) == EXPECTED_LINKS
    for href, title in EXPECTED_LINKS[3:5]:
        assert f'href="{href}"' in TODAY
        assert f'href="{href}"' in QUICK
        assert SHEET.count(f'href="{href}"') == 1
        assert title in SHEET
    assert "data-quick528-choices" in SHEET
    assert 'href="/quick-entry">All actions</a>' in SHEET


def test_701_existing_three_quick_save_forms_and_security_are_unchanged():
    for marker in (
        'data-quick528-form="weight"',
        'data-quick528-form="bp"',
        'data-quick528-form="water"',
    ):
        assert SHEET.count(marker) == 1
    assert SHEET.count('data-quick528-form=') == 3
    assert SHEET.count('data-quick528-endpoint="/vitals"') == 2
    assert SHEET.count('data-quick528-endpoint="/food/water"') == 1
    assert SHEET.count('type="submit"') == 3
    assert SHEET.count("method=\"post\"") == 3
    assert "data-quick528-success" in SHEET
    assert "aria-modal=\"true\"" in SHEET
    assert 'credentials: "same-origin"' in JS
    assert "new FormData(form)" in JS
    assert "localStorage" not in JS
    assert 'tracker-mobile-quick528.js?v=528' in BASE
    assert 'tracker-mobile-quick528.css?v=528' in BASE


def test_701_template_and_mobile_grid_maintain_accessible_controls():
    Environment().parse(SHEET)
    assert "grid-template-columns: repeat(2, minmax(0, 1fr))" in CSS
    assert ".tracker-quick528-choices .tracker-quick528-more" in CSS
    assert "grid-column: 1 / -1;" in CSS
    assert "min-height: 44px;" in CSS
    assert ":focus-visible" in CSS
    assert "env(safe-area-inset-bottom" in CSS


def test_701_preview_is_guarded_and_scoped():
    assert "BASE=405efb56dbf2c4a085149da8ba23fc1fd99729cf" in PREVIEW
    assert "REF=release/701-mobile-quick-add-actions" in PREVIEW
    assert "git diff --check" in PREVIEW
    assert 'app/templates/_mobile_quick528.html' in PREVIEW
    assert "tests/test_mobile_quick_actions701.py" in PREVIEW
    assert "tests/browser/test_mobile_quick_actions701.py" in PREVIEW
    assert 'TRACKER_DATA_DIR="$RUN/test-data"' in PREVIEW
    assert "RELEASE_701_PREVIEW=PASSED_ISOLATED_NO_INSTALL" in PREVIEW
    assert "RELEASE_701_QUICK_BROWSER=PASSED" in PREVIEW
