"""Release 759: unified 10,000-mcg display threshold in inventory views.

Only view presentation changes; canonical mass remains mcg for forecasts.
"""
from datetime import date
from pathlib import Path
from types import SimpleNamespace as S

from jinja2 import Environment
import pytest

from app.dashboard_forecast752 import build_dashboard_forecasts752
from app import units as U

ROOT = Path(__file__).resolve().parents[1]


def test_759_mass_threshold_is_exclusive_and_large_stock_remains_mg():
    assert U.fmt_amount(10_000, "mass") == "10,000 mcg"
    assert U.fmt_amount(10_001, "mass") == "10.001 mg"
    assert U.fmt_amount(36_349_664, "mass") == "36,349.664 mg"
    assert U.fmt_amount(-36_349_664, "mass") == "-36,349.664 mg"
    assert U.fmt_amount(2_500_000, "mass") == "2,500 mg"
    assert U.fmt_amount(500, "mass") == "500 mcg"
    assert U.fmt_amount(50, "iu") == "50 IU"
    assert U.fmt_amount(2, "volume") == "2 mL"


def test_759_dashboard_forecast_retains_base_units_and_original_runway():
    today = date(2026, 11, 23)
    compound = S(name="Synthetic Test C")
    item = S(compound_id=1, compound=compound, amount_value=48.0,
             amount_unit="mg", freq_count=3.0, freq_period="interval",
             start_week=1, end_week=None)
    protocol = S(id=1, name="Synthetic protocol", is_active=True,
                 items=[item], start_date=today, end_date=None)
    rows, low, watch = build_dashboard_forecasts752(
        [protocol], {1: {"mass": 36_349_664.0}}, today)
    assert len(rows) == len(watch) == 1
    assert low == []
    row = rows[0]
    assert row["dimension"] == "mass"
    assert row["remaining"] == 36_349_664.0
    assert row["unit"] == "mcg"
    assert row["days_left"] == pytest.approx(36_349_664.0 * 3 / 48_000)
    assert U.fmt_amount(row["remaining"], row["dimension"]) == "36,349.664 mg"


def test_759_dashboard_and_inventory_intelligence_use_mass_formatter():
    dashboard = (ROOT / "app/templates/dashboard.html").read_text()
    intelligence = (ROOT / "app/templates/inventory_intelligence.html").read_text()
    for template in (dashboard, intelligence):
        Environment().parse(template)
    assert "row.remaining|amt('mass')" in dashboard
    assert "row.dimension == 'mass'" in dashboard
    assert "item.remaining|amt('mass') if item.unit == 'mcg'" in dashboard
    assert "f.remaining|amt('mass') if f.unit == 'mcg'" in intelligence
    assert "f.used|amt('mass') if f.unit == 'mcg'" in intelligence
    assert "row.remaining|round(2) ~ ' ' ~ row.unit" not in dashboard
