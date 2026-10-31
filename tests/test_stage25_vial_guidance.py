"""Stage 25 inventory guidance regression tests."""

import ast
from pathlib import Path

from jinja2 import Environment


ROOT = Path(__file__).resolve().parents[1]

ROUTER = ROOT / "app/routers/doses.py"
TEMPLATE = ROOT / "app/templates/dose_workspace.html"


def test_router_parses():
    ast.parse(ROUTER.read_text())


def test_template_parses():
    Environment().parse(TEMPLATE.read_text())


def test_existing_vial_selection_preserved():
    source = TEMPLATE.read_text()
    assert "vial_id={{ vial.id }}" in source


def test_inventory_guidance_present():
    source = ROUTER.read_text()
    assert "vial_guidance" in source
    assert "recommended_vial_id" in source


def test_existing_inventory_service_preserved():
    source = ROUTER.read_text()
    assert "services.vial_views" in source


def test_planned_dose_conversion_uses_existing_units():
    source = ROUTER.read_text()
    assert "U.amount_to_vial_base" in source


def test_recommendation_does_not_record_dose():
    source = ROUTER.read_text()

    start = source.index(
        '@router.get("/dose-workspace")'
    )

    section = source[start:]

    assert "db.add(" not in section
    assert "db.commit(" not in section


def test_searchable_workspace_preserved():
    source = TEMPLATE.read_text()

    assert 'id="tracker-vial-search"' in source
    assert "data-tracker-vial-row" in source


def test_calendar_handoff_preserved():
    source = TEMPLATE.read_text()

    assert "planned_params.items()" in source
    assert "vial_id={{ vial.id }}" in source
