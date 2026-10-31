"""Stage 33: UI regression contracts.

These tests protect previously repaired behavior without
modifying application code.
"""

import re
from pathlib import Path

from jinja2 import Environment


ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = ROOT / "app/templates"
STATIC = ROOT / "app/static"


def test_vials_page_title_contains_no_markup():
    source = (TEMPLATES / "vials.html").read_text()

    match = re.search(
        r"{%\s*block\s+title\s*%}(.*?){%\s*endblock\s*%}",
        source,
        re.DOTALL,
    )

    assert match, "Vials title block missing"
    assert match.group(1).strip() == "Vials"


def test_vials_sorting_controls_preserved():
    source = (TEMPLATES / "vials.html").read_text()

    assert 'id="tracker-vials-sortable"' in source
    assert 'id="bulk-all"' in source

    for key in (
        "compound", "vial", "remaining", "amount",
        "landed", "cost", "coa", "status"
    ):
        assert f'data-vial-sort="{key}"' in source


def test_vials_sorting_script_preserved():
    template = (TEMPLATES / "vials.html").read_text()
    script = STATIC / "js/tracker-vials-sort.js"

    assert "tracker-vials-sort.js" in template
    assert script.is_file()
    assert "addEventListener('click'" in script.read_text()


def test_workspace_sorting_attributes_match_javascript():
    template = (TEMPLATES / "dose_workspace.html").read_text()
    script = (STATIC / "tracker_dose_workspace.js").read_text()

    for key in (
        "compound", "vial", "status", "remaining",
        "first-used", "beyond-use", "expires"
    ):
        assert f'data-tracker-sort-key="{key}"' in template
        assert f'data-tracker-{key}=' in template

    assert "row.dataset['tracker' +" in script
    assert "function sortRows()" in script


def test_workspace_search_handler_preserved():
    script = (STATIC / "tracker_dose_workspace.js").read_text()

    assert "addEventListener('input', update)" in script
    assert "fetch(" not in script
    assert "XMLHttpRequest" not in script


def test_modified_templates_parse():
    environment = Environment()

    for name in ("vials.html", "dose_workspace.html"):
        environment.parse((TEMPLATES / name).read_text())
