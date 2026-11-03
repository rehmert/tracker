"""Vitals create/edit interaction parity."""

from pathlib import Path

from app.templating import templates

ROOT = Path(__file__).resolve().parents[1]


def source(path):
    return (ROOT / path).read_text()


def test_both_forms_opt_in():
    add = source("app/templates/vitals.html")
    edit = source("app/templates/vitals_edit.html")

    assert 'data-tracker-vitals-entry="create"' in add
    assert 'data-tracker-vitals-entry="edit"' in edit

    assert "tracker-vitals-entry.js" in add
    assert "tracker-vitals-entry.js" in edit


def test_shared_behavior():
    js = source("app/static/js/tracker-vitals-entry.js")

    for feature in (
        "form[data-tracker-vitals-entry]",
        "mode === 'edit'",
        "Updated Reading:",
        "Ready to Record:",
        "Use Current Time",
        "setCustomValidity",
        "reportValidity()",
        "submitting = true",
        "Saving Changes",
    ):
        assert feature in js


def test_edit_can_clear_measurements():
    js = source("app/static/js/tracker-vitals-entry.js")

    assert "!editing && !state.hasMeasurement" in js
    assert "Saving will clear recorded measurements" in js


def test_no_extra_network_or_storage_calls():
    js = source("app/static/js/tracker-vitals-entry.js")

    for forbidden in (
        "fetch(",
        "XMLHttpRequest",
        "localStorage",
        "sessionStorage",
    ):
        assert forbidden not in js


def test_templates_parse():
    templates.env.get_template("vitals.html")
    templates.env.get_template("vitals_edit.html")
