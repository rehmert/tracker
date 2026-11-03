"""Vitals editing unsaved-changes protection."""

from pathlib import Path

from app.templating import templates

ROOT = Path(__file__).resolve().parents[1]


def read(path):
    return (ROOT / path).read_text()


def test_assets_scoped_to_edit():
    edit = read("app/templates/vitals_edit.html")
    create = read("app/templates/vitals.html")

    assert "tracker-vitals-edit-guard.js" in edit
    assert "tracker-vitals-edit-guard.css" in edit
    assert "data-vitals-edit-cancel" in edit
    assert "tracker-vitals-edit-guard.js" not in create


def test_dirty_check_and_restore():
    js = read(
        "app/static/js/tracker-vitals-edit-guard.js"
    )

    for token in (
        "function isDirty()",
        "Restore Original Values",
        "Unsaved Changes",
        "No Unsaved Changes",
        "beforeunload",
        "Discard unsaved changes",
        "event.defaultPrevented",
        "form.checkValidity()",
        "pageshow",
    ):
        assert token in js


def test_read_only_browser_behavior():
    js = read(
        "app/static/js/tracker-vitals-edit-guard.js"
    )

    for forbidden in (
        "fetch(",
        "XMLHttpRequest",
        "localStorage",
        "sessionStorage",
    ):
        assert forbidden not in js


def test_template_parses():
    templates.env.get_template("vitals_edit.html")
