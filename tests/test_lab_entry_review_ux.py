"""Lab entry completeness review and safe navigation."""

from pathlib import Path

from app.templating import templates

ROOT = Path(__file__).resolve().parents[1]


def read(path):
    return (ROOT / path).read_text()


def test_lab_entry_methods_preserved():
    html = read("app/templates/lab_form.html")

    for marker in (
        'action="/labs/import-csv"',
        'action="/labs"',
        'id="lab-csv-entry"',
        'id="lab-manual-entry"',
        "data-lab-manual-entry",
        "data-lab-entry-review",
        'id="lab-rows"',
        'hx-get="/labs/row"',
    ):
        assert marker in html


def test_review_checks_completeness():
    js = read(
        "app/static/js/tracker-lab-entry-review.js"
    )

    for marker in (
        "function reviewRows()",
        "complete++",
        "incomplete++",
        "partialRanges++",
        "reversedRanges++",
        "row.dataset.labReviewState",
        "htmx:afterSwap",
        "queueMicrotask(reviewRows)",
    ):
        assert marker in js


def test_read_only_review():
    js = read(
        "app/static/js/tracker-lab-entry-review.js"
    )

    for forbidden in (
        "fetch(",
        "XMLHttpRequest",
        "localStorage",
        "sessionStorage",
        "requestSubmit(",
        ".submit(",
        ".value =",
    ):
        assert forbidden not in js


def test_quick_entry_shortcut():
    quick = read("app/templates/quick_entry.html")
    lab = read("app/templates/lab_form.html")

    assert (
        'href="/labs/new#lab-manual-entry"'
        in quick
    )
    assert 'id="lab-manual-entry"' in lab


def test_templates_parse():
    templates.env.get_template("lab_form.html")
    templates.env.get_template("quick_entry.html")
