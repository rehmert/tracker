"""Regression contracts for the read-only workbench bundle."""
from datetime import date
from pathlib import Path
from types import SimpleNamespace

import pytest
from jinja2 import Environment

from app.pk_workbench import (
    ExperimentInput, schedule_doses,
)

ROOT = Path(__file__).resolve().parents[1]


def sample_protocol():
    item = SimpleNamespace(
        compound_id=5,
        amount_value=5,
        amount_unit="mg",
        freq_count=1,
        freq_period="week",
        start_week=1,
        end_week=None,
        dose_days="",
        dose_time="09:00",
    )
    return SimpleNamespace(items=[item])


def test_saved_schedule_is_not_mutated():
    protocol = sample_protocol()
    anchor = date(2026, 11, 1)

    baseline = schedule_doses(
        protocol, 5, anchor, 28
    )
    modified = schedule_doses(
        protocol, 5, anchor, 28,
        dose_multiplier=2,
        interval_multiplier=0.5,
    )

    assert len(baseline) == 4
    assert len(modified) == 8
    assert baseline[0][1] == 5
    assert modified[0][1] == 10

    assert protocol.items[0].amount_value == 5
    assert protocol.items[0].freq_count == 1


def test_fixed_weekday_interval_change_is_rejected():
    protocol = sample_protocol()
    protocol.items[0].dose_days = "0"

    with pytest.raises(
        ValueError, match="fixed-weekday"
    ):
        schedule_doses(
            protocol, 5, date(2026, 11, 1),
            28, interval_multiplier=2,
        )


def test_experiment_parameters_are_bounded():
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        ExperimentInput(
            compound_id=5,
            dose_multiplier=100,
        )
    with pytest.raises(ValidationError):
        ExperimentInput(
            compound_id=5,
            horizon_days=10000,
        )


def test_workbench_ui_and_read_only_endpoint():
    html = (
        ROOT / "app/templates/protocol_edit.html"
    ).read_text()
    js = (
        ROOT / "app/static/js/"
        "tracker-pk-workbench.js"
    ).read_text()
    endpoint = (
        ROOT / "app/routers/pk.py"
    ).read_text()

    assert 'id="pkExperimentWorkbench"' in html
    assert 'id="pkExpRun"' in html
    assert 'id="pkExpReset"' in html
    assert 'id="pkExpPlot"' in html

    assert "tracker-pk-workbench.js?v=bundle63" in html
    assert "trackerPkInspector" in js
    assert "trackerPkAxes" in js
    assert "pkExpInventory" in js
    assert "pkExpLabs" in js

    assert '@router.post("/workbench/{pid}")' in endpoint

    Environment().parse(html)


def test_workbench_has_no_write_calls():
    source = (
        ROOT / "app/pk_workbench.py"
    ).read_text()

    for forbidden in (
        "db.add(",
        "db.delete(",
        "db.commit(",
        "db.flush(",
    ):
        assert forbidden not in source
