"""Stage 34.2 inventory attention contracts."""

from pathlib import Path

from jinja2 import Environment

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = (
    ROOT / "app/templates/vials.html"
).read_text()

SCRIPT = (
    ROOT / "app/static/js/tracker-vial-attention.js"
).read_text()


def test_attention_controls_exist():
    for identifier in (
        "tracker-vial-attention",
        "tracker-attention-expired",
        "tracker-attention-soon",
        "tracker-attention-low",
        "tracker-attention-depleted",
    ):
        assert f'id="{identifier}"' in TEMPLATE


def test_existing_table_preserved():
    assert 'id="tracker-vials-sortable"' in TEMPLATE
    assert 'id="bulk-vials"' in TEMPLATE
    assert 'id="bulk-all"' in TEMPLATE
    assert 'id="tracker-vial-quick-find"' in TEMPLATE


def test_attention_uses_existing_inventory_fields():
    for field in (
        "data-attention-status",
        "data-attention-remaining",
        "data-attention-percent",
        "data-attention-expires",
        "data-attention-beyond-use",
    ):
        assert field in TEMPLATE


def test_attention_is_read_only():
    assert "fetch(" not in SCRIPT
    assert "XMLHttpRequest" not in SCRIPT
    assert ".submit(" not in SCRIPT
    assert ".checked =" not in SCRIPT
    assert "SOON_DAYS = 30" in SCRIPT
    assert "LOW_PERCENT = 20" in SCRIPT


def test_template_parses():
    Environment().parse(TEMPLATE)
