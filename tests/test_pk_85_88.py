import random
from datetime import date, datetime
from pathlib import Path
from types import SimpleNamespace

from jinja2 import Environment
from app.pk_precision import schedule_doses
from app.pk_inventory_events import allocate_events


def test_randomized_exact_intervals():
    rng=random.Random(20261104)
    for _ in range(100):
        interval=rng.choice([
            .5,1,2,3,3.5,6,7
        ])
        item=SimpleNamespace(
            compound_id=1,amount_value=2,
            amount_unit="mg",
            freq_count=interval,
            freq_period="interval",
            start_week=1,end_week=None,
            dose_days="",dose_time="08:00",
        )
        ds=schedule_doses(
            SimpleNamespace(items=[item]),
            1,date(2026,11,4),14,
        )
        assert all(
            abs(
                (b[0]-a[0]).total_seconds()
                -interval*86400
            )<.01
            for a,b in zip(ds,ds[1:])
        )


def test_randomized_inventory_conservation():
    rng=random.Random(12)
    for _ in range(60):
        demand=rng.uniform(.1,20)
        supply=rng.uniform(.1,20)
        stock=[{
            "remaining_mg":supply,
            "expires_on":None,
            "beyond_use_on":None,
            "status":"sealed",
            "closed_on":None,
        }]
        result=allocate_events(
            stock,
            [(datetime(2026,11,6,8),demand)],
            date(2026,11,4),
            date(2026,12,4),
        )
        assert result["demand_reconciled"]
        assert abs(
            result["total_allocated_mg"]
            +result["total_unfilled_mg"]
            -result["demand_mg"]
        )<.00003


def test_dashboard_and_report_contracts():
    html=Path(
        "app/templates/pk_workspace.html"
    ).read_text()
    detail=Path(
        "app/templates/protocol_edit.html"
    ).read_text()

    for page in (html,detail):
        Environment().parse(page)

    assert 'data-pk-panel="protocols"' in html
    assert "tracker-pk-dashboard.js?v=bundle88" in html
    assert 'id="pkExpReportText"' in detail
    assert "tracker-pk-bundle88.css?v=bundle88" in detail
