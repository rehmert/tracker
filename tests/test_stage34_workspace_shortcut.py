"""Stage 34.4 Dose Workspace shortcut contracts."""

from pathlib import Path

from jinja2 import Environment

ROOT = Path(__file__).resolve().parents[1]

TEMPLATE = (
    ROOT / "app/templates/dose_workspace.html"
).read_text()

SCRIPT = (
    ROOT / "app/static/js/"
    "tracker-workspace-shortcut.js"
).read_text()


def test_shortcut_controls():
    assert (
        'id="tracker-workspace-shortcut"'
        in TEMPLATE
    )

    assert (
        'id="tracker-workspace-jump"'
        in TEMPLATE
    )

    assert (
        'id="tracker-workspace-suggestion"'
        in TEMPLATE
    )


def test_script_registered():
    assert (
        'tracker-workspace-shortcut.js?v=1'
        in TEMPLATE
    )


def test_existing_workspace_preserved():
    for identifier in (
        "tracker-vial-search",
        "tracker-available-vials",
        "tracker-vial-clear",
        "tracker-vial-count",
    ):
        assert f'id="{identifier}"' in TEMPLATE

    assert 'data-tracker-recommended=' in TEMPLATE
    assert 'data-tracker-sort-key=' in TEMPLATE


def test_shortcut_is_read_only():
    assert 'trackerRecommended="1"' not in SCRIPT

    assert (
        '[data-tracker-recommended="1"]'
        in SCRIPT
    )

    assert "scrollIntoView" in SCRIPT

    for forbidden in (
        "fetch(",
        "XMLHttpRequest",
        ".submit(",
        "row.remove(",
        "appendChild(suggested)",
        ".checked =",
    ):
        assert forbidden not in SCRIPT


def test_template_parses():
    Environment().parse(TEMPLATE)
