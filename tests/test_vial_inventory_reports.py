"""Preserve the inventory report behavior during layout consolidation."""

from pathlib import Path

from jinja2 import Environment

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "app/templates/vials.html"


def report_markup():
    text = TEMPLATE.read_text()

    start = text.index(
        "<!-- TRACKER_INVENTORY_REPORTS_CONSOLIDATED -->"
    )

    end = text.index(
        "<!-- END_TRACKER_INVENTORY_REPORTS_CONSOLIDATED -->",
        start,
    )

    return text[start:end]


def test_inventory_reports_collapsed_by_default():
    markup = report_markup()

    assert 'id="tracker-inventory-reports"' in markup
    assert "<summary>" in markup
    assert "<strong>Inventory reports</strong>" in markup
    assert 'id="tracker-inventory-reports" open' not in markup


def test_original_reports_are_preserved():
    markup = report_markup()

    for marker in (
        'id="tracker-vial-lifecycle"',
        'id="tracker-compound-inventory"',
        "tracker-vial-lifecycle.js",
        "tracker-compound-inventory.js",
        "tracker-vial-lifecycle.css",
        "tracker-compound-inventory.css",
        'id="tracker-lifecycle-filter"',
        'id="tracker-ci-search"',
        'id="tracker-ci-sort"',
    ):
        assert markup.count(marker) == 1, marker


def test_attention_remains_outside_collapsed_reports():
    text = TEMPLATE.read_text()
    markup = report_markup()

    assert 'id="tracker-vial-attention"' in text
    assert 'id="tracker-vial-attention"' not in markup

    assert text.index('id="tracker-vial-attention"') < (
        text.index('id="tracker-inventory-reports"')
    )


def test_primary_vial_workflow_preserved():
    text = TEMPLATE.read_text()

    for marker in (
        'id="tracker-vials-sortable"',
        'id="bulk-selection-toolbar"',
        'id="bulk-editor-panel"',
        'id="bulk-advanced-selection"',
        'id="tracker-vial-quick-find"',
        'id="bulk-delete-selected"',
    ):
        assert text.count(marker) == 1, marker


def test_report_scripts_remain_read_only():
    for filename in (
        "tracker-vial-lifecycle.js",
        "tracker-compound-inventory.js",
    ):
        text = (
            ROOT / "app/static/js" / filename
        ).read_text()

        assert "fetch(" not in text
        assert "requestSubmit(" not in text


def test_template_and_server_validation():
    Environment().parse(TEMPLATE.read_text())

    server = (
        ROOT / "app/routers/vials.py"
    ).read_text()

    assert "def _bulk_validate(" in server
    assert "def _bulk_snapshot(" in server
    assert '"/vials/bulk/preview"' in server
