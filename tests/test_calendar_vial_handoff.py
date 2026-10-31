"""Calendar -> Dose Workspace -> recording handoff."""

import ast
import html
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import parse_qs, urlsplit

from jinja2 import Environment


ROOT = Path(__file__).resolve().parents[1]

CALENDAR = ROOT / "app/templates/calendar.html"
WORKSPACE = ROOT / "app/templates/dose_workspace.html"
ROUTER = ROOT / "app/routers/doses.py"


def test_calendar_has_both_actions():
    source = CALENDAR.read_text()

    Environment().parse(source)

    assert "Log this dose" in source
    assert "Choose vial first" in source
    assert "/dose-workspace?compound_id=" in source


def test_workspace_preserves_vial_selection():
    source = WORKSPACE.read_text()

    Environment().parse(source)

    # Preserve the existing recording route and vial ID.
    assert "vial_id={{ vial.id }}" in source
    assert "/doses?compound_id=" in source

    # Preserve calendar context.
    assert "planned_params.items()" in source


def test_workspace_route_accepts_calendar_context():
    tree = ast.parse(ROUTER.read_text())

    functions = [
        node for node in tree.body
        if isinstance(node, ast.FunctionDef)
        and node.name == "dose_workspace"
    ]

    assert len(functions) == 1

    arguments = {
        arg.arg for arg in functions[0].args.args
    }

    assert {
        "compound_id",
        "planned_date",
        "planned_time",
        "planned_amount",
        "planned_unit",
    }.issubset(arguments)


def test_workspace_route_passes_context_to_template():
    tree = ast.parse(ROUTER.read_text())

    function = next(
        node for node in tree.body
        if isinstance(node, ast.FunctionDef)
        and node.name == "dose_workspace"
    )

    render_calls = [
        node for node in ast.walk(function)
        if isinstance(node, ast.Call)
        and any(
            keyword.arg == "planned_params"
            for keyword in node.keywords
        )
    ]

    assert render_calls


def test_vial_link_carries_planned_values():
    """Render the actual vial link, then inspect its URL."""

    source = WORKSPACE.read_text()

    start = source.index(
        '<a href="/doses?compound_id={{ vial.compound_id }}'
    )

    end = source.index("</a>", start) + len("</a>")

    fragment = source[start:end]

    template = Environment(
        autoescape=True
    ).from_string(fragment)

    vial = SimpleNamespace(
        id=42,
        compound_id=7,
    )

    rendered = template.render(
        vial=vial,
        planned_params={
            "planned_date": "2026-11-02",
            "planned_time": "14:30",
            "planned_amount": "2.5",
            "planned_unit": "mg",
        },
    )

    href = rendered.split('href="', 1)[1].split('"', 1)[0]
    url = urlsplit(html.unescape(href))
    params = parse_qs(url.query)

    assert url.path == "/doses"
    assert params["compound_id"] == ["7"]
    assert params["vial_id"] == ["42"]
    assert params["planned_date"] == ["2026-11-02"]
    assert params["planned_time"] == ["14:30"]
    assert params["planned_amount"] == ["2.5"]
    assert params["planned_unit"] == ["mg"]


def test_compound_filter_preserves_planned_values():
    source = WORKSPACE.read_text()

    assert 'action="/dose-workspace"' in source
    assert 'name="{{ key }}"' in source
    assert 'value="{{ value }}"' in source


def test_existing_dose_recording_endpoint_preserved():
    source = ROUTER.read_text()

    assert '@router.post("/doses")' in source
    assert '@router.post("/doses/preview")' in source
