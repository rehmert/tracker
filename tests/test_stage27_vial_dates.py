"""Stage 27 vial date visibility tests."""

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


def test_date_columns_present():
    source = TEMPLATE.read_text()

    assert "<th>First used</th>" in source
    assert "<th>Beyond-use</th>" in source
    assert "<th>Expires</th>" in source


def test_missing_dates_are_explicit():
    source = TEMPLATE.read_text()

    assert "Not recorded" in source


def test_date_context_passed():
    source = ROUTER.read_text()

    assert "vial_date_details=vial_date_details" in source


def test_recommendation_explanation_present():
    source = TEMPLATE.read_text()

    assert "recommended_reason" in source


def test_vial_recording_link_preserved():
    source = TEMPLATE.read_text()

    assert "vial_id={{ vial.id }}" in source


def test_calendar_handoff_preserved():
    source = TEMPLATE.read_text()

    assert "planned_params.items()" in source


def test_search_preserved():
    source = TEMPLATE.read_text()

    assert "tracker-vial-search" in source
