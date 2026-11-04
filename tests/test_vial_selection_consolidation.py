"""Preserve existing vial selection functionality during UI consolidation."""

from pathlib import Path
from jinja2 import Environment

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "app/templates/vials.html"
MANAGER = ROOT / "app/static/js/tracker-bulk-selection.js"


def advanced_section():
    text = TEMPLATE.read_text()
    start = text.index("<!-- TRACKER_BULK_STAGE7 -->")
    end = text.index(
        "<!-- STAGE34_VIAL_QUICK_FIND -->",
        start
    )
    return text[start:end]


def test_advanced_selection_is_collapsed_by_default():
    section = advanced_section()
    assert '<details id="bulk-advanced-selection">' in section
    assert '<details id="bulk-advanced-selection" open' not in section
    assert "Advanced selection &amp; CSV export" in section
    assert section.count("</details>") == 1


def test_all_advanced_actions_remain_present():
    section = advanced_section()
    for identifier in (
        "bulk7-compound",
        "bulk7-status",
        "bulk7-select",
        "bulk7-invert",
        "bulk7-clear",
        "bulk7-deselect",
        "bulk7-export",
        "bulk7-summary",
    ):
        assert section.count(
            f'id="{identifier}"'
        ) == 1


def test_primary_actions_remain_accessible():
    text = TEMPLATE.read_text()
    for identifier in (
        "bulk-selection-toolbar",
        "bulk-select-all",
        "bulk-select-none",
        "bulk-undo-selection",
        "bulk-open-editor",
        "bulk-delete-selected",
        "tracker-vial-quick-find",
    ):
        assert text.count(
            f'id="{identifier}"'
        ) == 1


def test_cross_view_selection_manager_is_unchanged():
    text = MANAGER.read_text()
    for marker in (
        "const LIMIT = 1000;",
        "function commitVisible()",
        "function sync()",
        "'bulk7-select'",
        "'bulk7-invert'",
        "'bulk7-clear'",
        "'bulk7-deselect'",
        "'bulk7-export'",
    ):
        assert marker in text


def test_template_and_bulk_safety():
    Environment().parse(TEMPLATE.read_text())
    server = (ROOT / "app/routers/vials.py").read_text()
    assert "def _bulk_snapshot(" in server
    assert "def _bulk_validate(" in server
    assert '"/vials/bulk/preview"' in server
    assert '"/vials/bulk/delete-preview"' in server
