"""Stage 28 sortable inventory regression checks."""

from pathlib import Path

from jinja2 import Environment


ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "app/templates/dose_workspace.html"
JS = ROOT / "app/static/tracker_dose_workspace.js"


def test_template_parses():
    Environment().parse(TEMPLATE.read_text())


def test_sortable_headers_present():
    source = TEMPLATE.read_text()

    for key in (
        "compound",
        "vial",
        "status",
        "remaining",
        "first-used",
        "beyond-use",
        "expires",
    ):
        assert f'data-tracker-sort-key="{key}"' in source


def test_row_sort_metadata_present():
    source = TEMPLATE.read_text()

    for key in (
        "recommended",
        "compound",
        "vial",
        "status",
        "remaining",
        "first-used",
        "beyond-use",
        "expires",
    ):
        assert f'data-tracker-{key}=' in source


def test_recommendation_reason_visible():
    source = TEMPLATE.read_text()

    assert "tracker-recommendation-reason" in source
    assert "{{ recommended_reason }}" in source


def test_vial_handoff_preserved():
    source = TEMPLATE.read_text()

    assert "vial_id={{ vial.id }}" in source
    assert "planned_params.items()" in source


def test_search_preserved():
    source = TEMPLATE.read_text()
    script = JS.read_text()

    assert 'id="tracker-vial-search"' in source
    assert "function update()" in script
    assert "addEventListener('input', update)" in script

def test_other_tables_unchanged():
    source = TEMPLATE.read_text()

    start = source.index(
        '<h2>Recent administrations</h2>'
    )

    section = source[start:]

    assert "<th>Compound</th>" in section
    assert "data-tracker-sort-key" not in section
