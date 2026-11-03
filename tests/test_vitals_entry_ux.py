"""Vitals entry UX regression coverage."""

from pathlib import Path

from app.templating import templates

ROOT = Path(__file__).resolve().parents[1]


def test_assets_registered():
    html = (
        ROOT / "app/templates/vitals.html"
    ).read_text()

    assert html.count("tracker-vitals-entry.js") == 1
    assert html.count("tracker-vitals-entry.css") == 1
    assert 'type="submit">Save reading' in html


def test_entry_validation():
    js = (
        ROOT /
        "app/static/js/tracker-vitals-entry.js"
    ).read_text()

    for token in (
        "Use Current Time",
        "localTimestamp",
        "Ready to Record:",
        "setCustomValidity",
        "reportValidity()",
        "partialBP",
        "hasMeasurement",
        "submitting = true",
    ):
        assert token in js


def test_no_extra_database_or_storage_calls():
    js = (
        ROOT /
        "app/static/js/tracker-vitals-entry.js"
    ).read_text()

    for forbidden in (
        "fetch(",
        "XMLHttpRequest",
        "localStorage",
        "sessionStorage",
    ):
        assert forbidden not in js


def test_accessibility():
    js = (
        ROOT /
        "app/static/js/tracker-vitals-entry.js"
    ).read_text()

    assert "aria-live" in js
    assert "role', 'alert" in js


def test_template_parses():
    templates.env.get_template("vitals.html")
