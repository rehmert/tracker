"""Release 586: shared form sizing and dose source vial contract."""
from pathlib import Path
from jinja2 import Environment

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "app/templates/base.html"
DOSES = ROOT / "app/templates/doses.html"
ROWS = ROOT / "app/templates/_dose_rows.html"
EDIT = ROOT / "app/templates/dose_edit.html"
CSS = ROOT / "app/static/css/tracker-form-overlap586.css"
BROWSER = ROOT / "tests/browser/test_form_overlap586.py"
QUALIFIER = ROOT / "scripts/tracker-browser-qualify.sh"
NAV = ROOT / "tests/browser/test_navigation.py"


def test_586_shared_styles_load_last_and_preserve_other_stylesheets():
    base = BASE.read_text(encoding="utf-8")
    assert base.count("tracker-form-overlap586.css?v=586") == 1
    assert base.index("tracker-form-overlap586.css?v=586") > base.index("/ui/theme.css")
    css = CSS.read_text(encoding="utf-8")
    for expected in (
        "minmax(min(100%, 13rem), 1fr)",
        "#main-content form.grid > *",
        "#main-content form .field > select",
        "min-width: 0;",
        "max-width: 100%;",
        'form#tracker-dose-correction-form .tracker-dose-when-field',
        'form[hx-post="/doses"] .tracker-dose-when-field',
        "@media (max-width: 960px)",
        "grid-template-columns: repeat(2, minmax(0, 1fr))",
    ):
        assert expected in css, expected


def test_586_edit_timestamp_uses_full_width_with_nonoverlapping_24h_controls():
    edit = EDIT.read_text(encoding="utf-8")
    assert 'class="field wide tracker-dose-when-field"' in edit
    assert 'name="taken_at"' in edit
    assert 'id="tracker-dose-correction-form"' in edit
    assert "tracker-time24-controls" in (
        ROOT / "app/static/js/tracker-time24-371.js"
    ).read_text(encoding="utf-8")
    assert "if width > 960:" in NAV.read_text(encoding="utf-8")
    Environment().parse(edit)


def test_586_dose_history_shows_permanent_vial_identity():
    doses = DOSES.read_text(encoding="utf-8")
    rows = ROWS.read_text(encoding="utf-8")
    assert "<th>Compound</th><th>Vial</th>" in doses
    assert 'href="/vials/{{ r.vial.id }}"' in rows
    assert "#{{ r.vial.id }}" in rows
    assert "{{ r.vial.label }}" in rows
    assert "Lot {{ r.vial.lot }}" in rows
    assert 'colspan="8"' in rows
    assert 'colspan="7"' not in rows
    for source in (doses, rows):
        Environment().parse(source)


def test_586_real_chromium_gate_covers_responsive_form_pages():
    source = QUALIFIER.read_text(encoding="utf-8")
    standard, strict = source.split("# Release 521: a second browser gate", 1)
    assert standard.count("tests/browser/test_form_overlap586.py") == 1
    assert "tests/browser/test_form_overlap586.py" not in strict
    browser = BROWSER.read_text(encoding="utf-8")
    for expected in (
        'TRACKER_TEST_ISOLATED', 'tracker-browser-qa',
        'test_586_key_form_pages_have_no_field_overlaps',
        'test_586_dose_edit_datetime_and_fields_do_not_overlap',
        'test_586_dose_history_shows_vial_identity',
        '(1440, 800, 390)', '(1440, 800, 390, 320)',
    ):
        assert expected in browser
