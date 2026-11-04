"""Guided bulk-editor requested-change review contracts."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "app/templates/vials.html"
JS = ROOT / "app/static/js/tracker-bulk-review-shortcuts.js"
CSS = ROOT / "app/static/css/tracker-bulk-review-shortcuts.css"


def test_review_surface_is_present():
    source = TEMPLATE.read_text()

    assert 'id="bulk-review-shortcut-status"' in source
    assert 'id="bulk-review-shortcut-list"' in source
    assert "tracker-bulk-review-shortcuts.js" in source
    assert "tracker-bulk-review-shortcuts.css" in source


def test_review_actions_do_not_submit_inventory():
    source = JS.read_text()

    assert 'element.type = "button"' in source
    assert "existing.click()" in source
    assert 'item.mode.value = "keep"' in source
    assert "form.requestSubmit(" not in source
    assert "fetch(" not in source


def test_review_handles_selection_and_missing_values():
    source = JS.read_text()

    assert 'bulk-toolbar-count' in source
    assert 'mode.value === "clear"' in source
    assert 'mode.value === "set" && !value' in source
    assert "tracker:bulk-selection-changed" in source
    assert "incomplete.length === 0" in source


def test_jump_reveals_hidden_fields_without_opt_in():
    source = JS.read_text()

    assert "panel.open = true" in source
    assert "onlyEdited.checked = false" in source
    assert "group.open = true" in source
    assert "item.field.scrollIntoView(" in source
    assert 'item.mode.value = "set"' not in source


def test_existing_server_review_is_unchanged():
    server = (
        ROOT / "app/routers/vials.py"
    ).read_text()

    assert "def _bulk_validate(" in server
    assert "def _bulk_snapshot(" in server
    assert '"/vials/bulk/preview"' in server
    assert CSS.exists()
