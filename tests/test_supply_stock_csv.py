"""Filtered Supplies stock CSV export regression tests."""

from pathlib import Path

from app.templating import templates

ROOT = Path(__file__).resolve().parents[1]


def read(path):
    return (ROOT / path).read_text()


def test_export_controls_registered():
    html = read("app/templates/supplies.html")

    assert "data-stock-export" in html
    assert "data-stock-print" in html
    assert "Export Filtered CSV" in html
    assert "Print Stock Review" in html
    assert "tracker-stock-filters.js?v=20261103-batch4" in html


def test_export_uses_filtered_rows():
    js = read(
        "app/static/js/tracker-stock-filters.js"
    )

    for token in (
        "rows.filter(",
        "!row.hidden",
        "rowForCsv",
        "csvValue",
        "createObjectURL",
        "revokeObjectURL",
        "text/csv;charset=utf-8",
        "window.print()",
    ):
        assert token in js


def test_export_excludes_sensitive_form_values():
    js = read(
        "app/static/js/tracker-stock-filters.js"
    )

    export_start = js.index("function rowForCsv")
    export_end = js.index(
        "exportButton.addEventListener",
        export_start
    )
    export_section = js[export_start:export_end]

    assert "cells[0]" in export_section
    assert "cells[3]" in export_section
    assert "data-stock-state" in export_section
    assert "cells[4]" not in export_section
    assert "cells[6]" not in export_section
    assert "submission_token" not in export_section
    assert ".value" not in export_section


def test_existing_usage_controls_preserved():
    html = read("app/templates/supplies.html")

    assert 'name="submission_token"' in html
    assert "data-tracker-supply-use" in html
    assert "data-stock-health-summary" in html
    assert "data-stock-review-row" in html
    assert "data-stock-status-filter" in html


def test_template_parses():
    templates.env.get_template("supplies.html")
