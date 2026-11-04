"""Bulk editor field-search safety and integration contracts."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "app/templates/vials.html"
SCRIPT = ROOT / "app/static/js/tracker-bulk-field-finder.js"
STYLE = ROOT / "app/static/css/tracker-bulk-field-finder.css"


def test_field_finder_is_wired():
    html = TEMPLATE.read_text()

    assert 'id="bulk-field-search"' in html
    assert 'id="bulk-field-search-clear"' in html
    assert 'id="bulk-field-search-status"' in html
    assert "tracker-bulk-field-finder.js" in html
    assert "tracker-bulk-field-finder.css" in html


def test_requested_changes_remain_visible():
    script = SCRIPT.read_text()

    assert 'fieldMode(field) !== "keep"' in script
    assert "const visible = matches || changed;" in script
    assert "field.hidden = !(visible && permitted)" in script


def test_empty_search_restores_group_visibility():
    script = SCRIPT.read_text()

    assert "originalOpen = new Map(" in script
    assert "group.hidden = visibleFields.length === 0" in script
    assert "group.open = originalOpen.get(group)" in script
    assert 'event.key === "Escape"' in script


def test_finder_never_submits_or_writes_inventory():
    script = SCRIPT.read_text()

    assert "fetch(" not in script
    assert "requestSubmit(" not in script
    assert "form.submit(" not in script
    assert 'input.value = "";' in script


def test_existing_server_validation_remains():
    server = (
        ROOT / "app/routers/vials.py"
    ).read_text()

    assert "def _bulk_validate(" in server
    assert "def _bulk_snapshot(" in server
    assert '"/vials/bulk/preview"' in server
    assert STYLE.exists()
