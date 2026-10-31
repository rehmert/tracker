"""Stage 34.3: interactive attention contracts."""

from pathlib import Path

from jinja2 import Environment

ROOT = Path(__file__).resolve().parents[1]

TEMPLATE = (
    ROOT / "app/templates/vials.html"
).read_text()

SCRIPT = (
    ROOT / "app/static/js/"
    "tracker-attention-navigation.js"
).read_text()


def test_navigation_script_registered():
    assert (
        'tracker-attention-navigation.js?v=1'
        in TEMPLATE
    )


def test_existing_features_preserved():
    for identifier in (
        "tracker-vials-sortable",
        "tracker-vial-attention",
        "tracker-vial-quick-find",
        "bulk-vials",
        "bulk-all",
    ):
        assert f'id="{identifier}"' in TEMPLATE


def test_attention_categories_supported():
    for key in (
        "expired",
        "soon",
        "low",
        "depleted",
    ):
        assert f"['{key}'," in SCRIPT


def test_navigation_preserves_row_visibility():
    assert "scrollIntoView" in SCRIPT
    assert "tracker-attention-match" in SCRIPT
    assert "tracker-attention-current" in SCRIPT

    for forbidden in (
        "fetch(",
        "XMLHttpRequest",
        ".submit(",
        ".checked =",
        "row.remove(",
        "row.hidden =",
        "row.style.display",
    ):
        assert forbidden not in SCRIPT


def test_template_parses():
    Environment().parse(TEMPLATE)
