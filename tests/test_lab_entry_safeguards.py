"""Lab report creation safeguards."""

from pathlib import Path

from app.templating import templates

ROOT = Path(__file__).resolve().parents[1]


def read(path):
    return (ROOT / path).read_text()


def test_both_entry_methods_preserved():
    html = read("app/templates/lab_form.html")

    for marker in (
        'action="/labs/import-csv"',
        'action="/labs"',
        'data-lab-csv-entry',
        'data-lab-manual-entry',
        'data-lab-entry-review',
        'data-lab-duplicate-warning',
        'id="lab-rows"',
        'hx-get="/labs/row"',
    ):
        assert marker in html


def test_unsaved_change_guard():
    js = read(
        "app/static/js/tracker-lab-entry-safeguards.js"
    )

    for marker in (
        "function snapshot(form)",
        "function isDirty()",
        "form.checkValidity()",
        "beforeunload",
        "pageshow",
        "window.confirm(",
        "original.get(form)",
    ):
        assert marker in js


def test_duplicate_analyte_review():
    js = read(
        "app/static/js/tracker-lab-entry-safeguards.js"
    )

    for marker in (
        "function reviewDuplicates()",
        'input[name="analyte"]',
        "toLocaleLowerCase()",
        "MutationObserver",
        "data-lab-duplicate",
        "Possible duplicate analytes:",
    ):
        assert marker in js


def test_no_record_writes():
    js = read(
        "app/static/js/tracker-lab-entry-safeguards.js"
    )

    for forbidden in (
        "fetch(",
        "XMLHttpRequest",
        "localStorage",
        "sessionStorage",
        "requestSubmit(",
        ".submit(",
    ):
        assert forbidden not in js


def test_quick_entry_csv_shortcut():
    quick = read("app/templates/quick_entry.html")
    lab = read("app/templates/lab_form.html")

    assert (
        'href="/labs/new#lab-csv-entry"'
        in quick
    )
    assert 'id="lab-csv-entry"' in lab


def test_templates_parse():
    templates.env.get_template("lab_form.html")
    templates.env.get_template("quick_entry.html")
