"""Dose Workspace vial-selection regression checks."""

from pathlib import Path
import ast

from jinja2 import Environment


ROOT = Path(__file__).resolve().parents[1]


def test_doses_page_accepts_vial_id():
    path = ROOT / "app/routers/doses.py"
    tree = ast.parse(path.read_text())

    functions = [
        node for node in tree.body
        if isinstance(node, ast.FunctionDef)
        and node.name == "doses_page"
    ]

    assert len(functions) == 1

    arguments = {
        arg.arg for arg in functions[0].args.args
    }

    assert "vial_id" in arguments


def test_dose_form_selects_exact_vial():
    source = (
        ROOT / "app/templates/doses.html"
    ).read_text()

    Environment().parse(source)

    assert "v.id == selected_vial_id" in source
    assert 'hx-trigger="load, input delay:200ms, change"' in source


def test_workspace_passes_vial_id():
    source = (
        ROOT / "app/templates/dose_workspace.html"
    ).read_text()

    Environment().parse(source)

    assert (
        "vial_id={{ vial.id }}" in source
        or 'record_url(vial)' in source
    )


def test_existing_recording_endpoint_preserved():
    source = (
        ROOT / "app/routers/doses.py"
    ).read_text()

    assert '@router.post("/doses")' in source
    assert '@router.post("/doses/preview")' in source
