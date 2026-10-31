"""Stage 34.1 inventory quick-find contracts."""

from pathlib import Path

from jinja2 import Environment

SOURCE = (
    Path(__file__).resolve().parents[1]
    / "app/templates/vials.html"
).read_text()


def test_quick_find_controls_exist():
    for identifier in (
        "tracker-vial-quick-find",
        "tracker-vial-find-count",
        "tracker-vial-find-next",
        "tracker-vial-find-clear",
    ):
        assert f'id="{identifier}"' in SOURCE


def test_quick_find_preserves_inventory_controls():
    for identifier in (
        "tracker-vials-sortable",
        "bulk-all",
        "bulk-vials",
        "bulk-selection-toolbar",
    ):
        assert f'id="{identifier}"' in SOURCE


def test_quick_find_is_non_destructive():
    section = SOURCE.split(
        "<!-- STAGE34_VIAL_QUICK_FIND -->", 1
    )[1].split(
        "<!-- END_STAGE34_VIAL_QUICK_FIND -->", 1
    )[0]

    assert "classList.add" in section
    assert "classList.remove" in section
    assert "scrollIntoView" in section

    assert "fetch(" not in section
    assert "XMLHttpRequest" not in section
    assert ".remove()" not in section


def test_template_parses():
    Environment().parse(SOURCE)
