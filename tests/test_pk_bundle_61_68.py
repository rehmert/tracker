"""Checks for the three bundled PK improvement phases."""
from datetime import date
from pathlib import Path
from types import SimpleNamespace

import pytest
from jinja2 import Environment

from app.pk_precision import schedule_doses
from app.pk_library import ExperimentSave, storage
from app.pk_workbench import ExperimentInput

ROOT=Path(__file__).resolve().parents[1]


def test_exact_interval_for_half_day():
    p=SimpleNamespace(items=[SimpleNamespace(
        compound_id=1,amount_value=1,
        amount_unit="mg",freq_count=0.5,
        freq_period="interval",start_week=1,
        end_week=None,dose_days="",dose_time="08:00"
    )])
    doses=schedule_doses(p,1,date(2026,11,1),2)
    assert len(doses)==4
    assert (doses[1][0]-doses[0][0]).total_seconds()==43200


def test_dose_edit_bounds():
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        ExperimentInput(
            compound_id=1,
            dose_edits=[{
                "index":1001,"action":"skip"
            }]
        )


def test_library_uses_backed_up_upload_storage(
    tmp_path, monkeypatch
):
    from app import config
    monkeypatch.setattr(config,"DATA_DIR",tmp_path)
    path=storage(8)
    assert path.parent == (
        tmp_path/"uploads"/"experiments"
    )


def test_workspace_and_templates():
    for name in ("pk_workspace.html","protocol_edit.html"):
        Environment().parse(
            (ROOT/"app/templates"/name).read_text()
        )
    router=(ROOT/"app/routers/pk.py").read_text()
    assert '@router.get("/workspace")' in router
    assert '@router.post("/library/{pid}")' in router
    assert '@router.post("/workbench/{pid}")' in router

    html=(ROOT/"app/templates/protocol_edit.html").read_text()
    assert 'id="pkExpDoseRows"' in html
    assert 'id="pkExpSaved"' in html
    assert "tracker-pk-library.js?v=bundle76" in html
