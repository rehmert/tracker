"""Keep saved-view behavior intact while simplifying the Vials header."""

from pathlib import Path
from jinja2 import Environment

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "app/templates/vials.html"
SAVED_VIEWS = ROOT / "app/static/vial_saved_views.js"


def page():
    return TEMPLATE.read_text()


def test_saved_view_picker_is_not_inside_disclosure():
    text = page()
    block = text[
        text.index('<div class="card" id="vial-saved-views"'):
        text.index('<p class="filters">')
    ]

    disclosure = block[
        block.index('<details id="vial-view-management">'):
        block.index("</details>")
    ]

    assert 'id="vial-view-picker"' in block
    assert 'id="vial-view-picker"' not in disclosure
    assert 'id="vial-view-save"' in disclosure
    assert 'id="vial-view-delete"' in disclosure
    assert '<details id="vial-view-management">' in block


def test_original_filter_contract_is_unchanged():
    text = page()

    for marker in (
        'id="vial-filter-form"',
        'name="status"',
        'name="compound_id"',
        'id="vial-view-picker"',
        'id="vial-view-message"',
        '<p class="filters">',
        "('active', 'In stock')",
        "('all', 'All')",
    ):
        assert marker in text


def test_saved_view_storage_logic_is_preserved():
    text = SAVED_VIEWS.read_text()

    assert "tracker.vials.savedViews.v1" in text
    assert "localStorage.getItem(KEY)" in text
    assert "localStorage.setItem(KEY" in text
    assert "location.assign('/vials?'" in text


def test_inventory_and_bulk_controls_remain():
    text = page()

    for identifier in (
        "tracker-vials-sortable",
        "bulk-selection-toolbar",
        "bulk-open-editor",
        "bulk-delete-selected",
        "tracker-vial-quick-find",
        "bulk-editor-panel",
    ):
        assert text.count(f'id="{identifier}"') == 1


def test_template_and_server_safety():
    Environment().parse(page())

    server = (
        ROOT / "app/routers/vials.py"
    ).read_text()

    assert "def _bulk_validate(" in server
    assert "def _bulk_snapshot(" in server
    assert '"/vials/bulk/preview"' in server
