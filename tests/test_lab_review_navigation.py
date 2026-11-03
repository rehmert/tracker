"""Navigation improvements must not alter lab records."""

from pathlib import Path

from app.templating import templates

ROOT = Path(__file__).resolve().parents[1]


def read(path):
    return (ROOT / path).read_text()


def test_report_picker_search():
    html = read("app/templates/lab_form.html")
    js = read("app/static/js/tracker-lab-navigation.js")

    for token in (
        'data-lab-source-search',
        'data-lab-source-count',
        'id="lab-source-report"',
        'method="get" action="/labs/new"',
    ):
        assert token in html

    for token in (
        "function setupSourceSearch()",
        "select.replaceChildren(",
        "stillAvailable ? selected : ''",
        "source reports",
    ):
        assert token in js


def test_incomplete_navigation():
    html = read("app/templates/lab_form.html")
    js = read("app/static/js/tracker-lab-navigation.js")

    assert "data-lab-find-incomplete" in html
    assert "data-lab-navigation-message" in html

    for token in (
        "function findProblem(row)",
        "analyte.value.trim()",
        "value.validity.valid",
        "unit.value.trim()",
        "hasLow !== hasHigh",
        "Number(low.value) > Number(high.value)",
        "target.focus()",
        "target.scrollIntoView(",
    ):
        assert token in js


def test_no_lab_record_writes():
    js = read("app/static/js/tracker-lab-navigation.js")

    for forbidden in (
        "fetch(",
        "XMLHttpRequest",
        "localStorage",
        "sessionStorage",
        "requestSubmit(",
        ".submit(",
    ):
        assert forbidden not in js


def test_existing_forms_and_safeguards():
    html = read("app/templates/lab_form.html")

    for token in (
        'action="/labs/import-csv"',
        'action="/labs"',
        'data-lab-csv-entry',
        'data-lab-manual-entry',
        'data-lab-entry-review',
        'data-lab-duplicate-warning',
        'id="lab-rows"',
        'hx-get="/labs/row"',
        "tracker-lab-entry-safeguards.js",
        "tracker-lab-entry-review.js",
    ):
        assert token in html


def test_template_parses():
    templates.env.get_template("lab_form.html")
