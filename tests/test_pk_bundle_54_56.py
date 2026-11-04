"""PK Releases 54–56 read-only integration contracts."""
import json
from datetime import date
from pathlib import Path
from types import SimpleNamespace

from app.models import Compound, Protocol
from app.routers import pk as pk_router
from jinja2 import Environment

ROOT = Path(__file__).resolve().parents[1]


class FakeDB:
    def __init__(self, p):
        self.p = p

    def get(self, model, identity):
        if model is Protocol:
            return self.p
        if model is Compound:
            return SimpleNamespace(name="Tirzepatide")
        return None


def test_saved_protocol_contains_dose_markers(monkeypatch):
    item = SimpleNamespace(
        compound_id=1, amount_value=5,
        amount_unit="mg", freq_count=1,
        freq_period="week", start_week=1,
        end_week=None, dose_days="",
        dose_time="09:00"
    )
    p = SimpleNamespace(
        name="Example", is_active=False,
        start_date=date(2026,11,1),
        end_date=None, horizon_weeks=2,
        items=[item]
    )
    monkeypatch.setattr(
        pk_router.pk, "series",
        lambda start,end,actual,planned,
        *args,**kwargs: [
            {"at":start.isoformat(),"planned":0},
            {"at":end.isoformat(),"planned":3}
        ]
    )
    response = pk_router.saved_protocol_exposure(
        1, db=FakeDB(p)
    )
    data = json.loads(response.body)
    assert response.status_code == 200
    assert data["status"] == "What-if"
    assert data["graphs"][0]["dose_count"] == 2
    doses = data["graphs"][0]["doses"]
    assert len(doses) == 2
    assert doses[0]["amount_mg"] == 5


def test_bundled_protocol_comparison_is_read_only():
    router = (
        ROOT / "app/routers/pk.py"
    ).read_text()
    editor = (
        ROOT / "app/templates/protocol_edit.html"
    ).read_text()
    compare = (
        ROOT / "app/static/js/"
        "tracker-protocol-compare.js"
    ).read_text()

    assert 'id="protocolCompareTarget"' in editor
    assert 'id="protocolCompareButton"' in editor
    assert "other_protocols" in (
        ROOT / "app/routers/protocols.py"
    ).read_text()
    assert "Promise.all([" in compare
    assert "sample(graph, elapsed)" in compare
    assert "trackerPkAxes.draw({" in compare
    assert 'method:"POST"' not in compare
    assert "db.commit()" not in router.split(
        '@router.get("/protocol-exposure/{pid}")'
    )[1].split('@router.get("/data")')[0]
    Environment().parse(editor)


def test_inspector_analysis_and_asset_links():
    engine = (
        ROOT / "app/static/js/"
        "tracker-pk-inspector.js"
    ).read_text()
    main = (ROOT / "app/static/pk.js").read_text()
    multi = (
        ROOT / "app/static/js/"
        "tracker-pk-multi-schedule.js"
    ).read_text()
    protocol = (
        ROOT / "app/static/js/"
        "tracker-protocol-exposure.js"
    ).read_text()
    html = (
        ROOT / "app/templates/pk.html"
    ).read_text()

    for marker in (
        "function analysis(times, values, doses = [])",
        "function trapezoid(",
        "pointermove",
        "pk-inspector-tooltip",
        "pk-inspector-dose",
        "function csv(times, series)",
        "Successive interval means within 5%",
    ):
        assert marker in engine

    assert main.count(
        "window.trackerPkInspector.attach("
    ) == 3
    assert "window.trackerPkInspector.attach(" in multi
    assert "inspector.attach(canvas,{" in protocol
    assert "tracker-pk-inspector.js?v=bundle56" in html
    Environment().parse(html)
