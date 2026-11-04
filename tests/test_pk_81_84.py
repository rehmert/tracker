from datetime import date, datetime
from types import SimpleNamespace
from pathlib import Path

from app.pk_library import (
    save, revise, listing, ExperimentSave
)
from app.pk_workbench import ExperimentInput


def test_snapshot_and_revisions(tmp_path, monkeypatch):
    from app import config
    monkeypatch.setattr(config,"DATA_DIR",tmp_path)

    item = SimpleNamespace(
        compound_id=1, amount_value=5,
        amount_unit="mg", freq_count=3.5,
        freq_period="interval", start_week=1,
        end_week=None, dose_days="", dose_time="08:00",
    )
    p = SimpleNamespace(
        name="Saved",start_date=date(2026,11,1),
        end_date=None,updated_at=datetime(2026,11,4),
        items=[item],
    )

    first=save(
        9,p,ExperimentSave(
            name="A",settings=ExperimentInput(compound_id=1)
        )
    )
    assert first["source_snapshot"]["items"][0][
        "freq_count"
    ]==3.5

    second=revise(
        9,first["id"],p,ExperimentSave(
            name="B",settings=ExperimentInput(compound_id=1)
        )
    )
    assert second["revisions"][0]["name"]=="A"
    assert len(listing(9))==1


def test_compare_routes_and_ui():
    router=Path("app/routers/pk.py").read_text()
    html=Path("app/templates/protocol_edit.html").read_text()
    assert '@router.post("/library/{pid}/compare")' in router
    assert '@router.put("/library/{pid}/{experiment_id}")' in router
    assert 'id="pkExpCompare"' in html
    assert 'id="pkExpReportText"' in html
