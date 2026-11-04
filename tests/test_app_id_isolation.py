"""Prevent reintroduction of fixed IDs in integration tests."""

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "tests/test_app.py"


def test_python_source_parses():
    ast.parse(PATH.read_text())


def test_dynamic_ids_are_queried():
    source = PATH.read_text()
    for marker in (
        "select(Compound.id)",
        "select(Vial.id)",
        "select(Page.id)",
        "select(LabReport.id)",
        "first_vial, second_vial = vial_ids",
    ):
        assert marker in source


def test_fixed_routes_are_absent():
    source = PATH.read_text()
    for marker in (
        '"/vials/1',
        '"/coas/1',
        '"/labs/1',
        '"/pages/2',
        '"compound_id": 1',
        '"vial_id": 1',
        '"compound_ids": [1]',
    ):
        assert marker not in source


def test_integration_scenarios_are_preserved():
    source = PATH.read_text()
    for marker in (
        "5 mg/mL",
        "$110.00",
        "$5.50",
        "COA uploaded",
        "Linked from",
        "Saved 2 result",
        "vs saved",
    ):
        assert marker in source
