"""Release 756 - real isolated ORM tests for concentration-aware forecasts.

These tests use in-memory SQLite and synthetic protocols, never live data.
"""
from datetime import date, datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import create_engine, select, func
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool
from jinja2 import Environment

from app.db import Base
from app.models import (Compound, Protocol, ProtocolItem, Vial,
                        DoseLog, Blend, BlendComponent)
from app.routers.inventory_forecast import (build_rows, weekly, normalized,
                                            compatible)
from app.routers.forecast_audit import audit_rows
from app.routers.forecast_horizons import compare_horizons
from app.routers.scheduled_forecast import build_schedule

TODAY = date.today()
ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def db():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False},
                           poolclass=StaticPool)
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    engine.dispose()


def plan(db, *, amount=0.2, unit="mL", interval=3, period="interval"):
    compound = Compound(name="Synthetic Test C", category="testosterone",
                        primary_unit="mg")
    db.add(compound)
    db.flush()
    protocol = Protocol(name="Synthetic q3d protocol", is_active=True,
                        start_date=TODAY-timedelta(days=2))
    db.add(protocol)
    db.flush()
    db.add(ProtocolItem(protocol_id=protocol.id, compound_id=compound.id,
                        position=0, amount_value=amount, amount_unit=unit,
                        freq_count=interval, freq_period=period,
                        start_week=1, dose_days="", dose_time=""))
    db.flush()
    return compound


def vial(db, compound, *, content=2400, unit="mg", liquid_ml=10,
         status="sealed", expiry=None, bud=None, closed=None):
    v = Vial(compound_id=compound.id, content_value=content,
             content_unit=unit, volume_ml=liquid_ml, status=status,
             form="solution", unit_price_cents=1000,
             expires_on=expiry, beyond_use_on=bud, closed_on=closed)
    db.add(v)
    db.flush()
    return v


def only_row(db, days=28):
    result = build_rows(db, days)
    assert len(result) == 1
    return result[0]


def test_756_test_c_ml_every_three_days_shows_real_vials_and_weeks(db):
    c = plan(db)
    vial(db, c, content=2400, liquid_ml=10)
    r = only_row(db)
    assert r["compound"] == "Synthetic Test C"
    assert r["vials"] == 1 and r["excluded"] == 0
    assert r["unit"] == "mL"
    assert r["available"] == pytest.approx(10)
    assert r["demand"] == pytest.approx(0.2 * 28 / 3)
    assert r["weeks"] == pytest.approx(10 / (0.2 * 7 / 3))
    assert r["status"] == "Roughly covered"


def test_756_volume_consumption_and_blend_transfers_not_double_subtracted(db):
    c = plan(db)
    v = vial(db,c)
    db.add(DoseLog(vial_id=v.id, taken_at=datetime.now(),
                   entered_value=2, entered_unit="mL",
                   amount_base=480000, kind="dose"))
    b = Blend(label="Synthetic blend", final_volume_ml=2.0,
              status="in_use")
    db.add(b)
    db.flush()
    db.add(BlendComponent(blend_id=b.id, source_vial_id=v.id,
                          compound_id=c.id, transferred_base=240000,
                          transferred_ml=1, target_dose_base=25000,
                          target_unit="mcg"))
    db.flush()
    r = only_row(db)
    assert r["available"] == pytest.approx(7)
    assert r["weeks"] == pytest.approx(7 / (0.2 * 7 / 3))


def test_756_missing_volume_is_unknown_not_false_zero(db):
    c=plan(db)
    vial(db,c,liquid_ml=None)
    r=only_row(db)
    assert r["vials"] == 0 and r["excluded"] == 1
    assert r["available"] is None
    assert r["demand"] == pytest.approx(0.2 * 28 / 3)
    assert r["weeks"] is None
    assert r["status"] == "Concentration unavailable"
    assert "concentration" in r["caveat"]
    a = audit_rows(db)
    assert a[0]["available"] is None
    assert a[0]["flag"] == "Review stock / concentration"
    h = compare_horizons(db)
    assert h[0]["available"] is None


def test_756_one_unknown_concentration_prevents_false_total_weeks(db):
    c=plan(db)
    vial(db,c)
    vial(db,c,liquid_ml=None)
    r=only_row(db)
    assert r["available"] == pytest.approx(10)
    assert r["vials"] == 1 and r["excluded"] == 1
    assert r["weeks"] is None
    assert r["status"] == "Volume data incomplete"
    assert audit_rows(db)[0]["flag"] == "Review concentration / coverage"


def test_756_mixed_concentrations_never_claim_interchangeable_weeks(db):
    c=plan(db)
    vial(db,c,content=2400,liquid_ml=10)
    vial(db,c,content=2000,liquid_ml=10)
    r=only_row(db)
    assert r["available"] == pytest.approx(20)
    assert r["vials"] == 2
    assert r["weeks"] is None
    assert r["status"] == "Mixed concentrations - review"
    assert "interchangeable" in r["caveat"]
    assert audit_rows(db)[0]["flag"] == "Review concentration / coverage"


def test_756_identical_concentrations_across_vials_add_up(db):
    c=plan(db)
    vial(db,c,content=2400,liquid_ml=10)
    vial(db,c,content=1200,liquid_ml=5)
    r=only_row(db)
    assert r["available"] == pytest.approx(15)
    assert r["vials"] == 2
    assert r["weeks"] == pytest.approx(15 / (0.2 * 7 / 3))


def test_756_expired_closed_discarded_vials_remain_excluded(db):
    c=plan(db)
    vial(db,c,expiry=TODAY-timedelta(days=1))
    vial(db,c,bud=TODAY-timedelta(days=1))
    vial(db,c,status="finished")
    vial(db,c,status="discarded")
    vial(db,c,closed=TODAY)
    r=only_row(db)
    assert r["vials"] == 0 and r["excluded"] == 5
    assert r["available"] == 0
    assert r["status"] == "No matching inventory"


def test_756_mass_based_forecasts_remain_in_mg(db):
    c=plan(db,amount=50,unit="mg",interval=1,period="week")
    vial(db,c,content=250,liquid_ml=None)
    r=only_row(db)
    assert r["unit"] == "mg"
    assert r["available"] == pytest.approx(250)
    assert r["demand"] == pytest.approx(200)
    assert r["weeks"] == pytest.approx(5)


def test_756_iu_vials_and_uL_volume_are_compatible(db):
    c=plan(db,amount=50,unit="uL",interval=3,period="interval")
    vial(db,c,content=2000,unit="IU",liquid_ml=2)
    r=only_row(db)
    assert r["unit"] == "mL" and r["vials"] == 1
    assert r["available"] == pytest.approx(2)
    assert r["demand"] == pytest.approx(0.05*28/3)
    assert compatible("IU", "uL")
    assert not compatible("IU", "mg")


@pytest.mark.parametrize("interval", [0, -1, float("nan"), float("inf")])
def test_756_invalid_interval_returns_unknown_demand(interval):
    # SQLite may normalize NaN to SQL NULL, so test invalid values in the
    # pure rate calculator without writing non-finite fixture values.
    from types import SimpleNamespace as Item
    item=Item(amount_value=0.2,amount_unit="mL",
              freq_count=interval,freq_period="interval")
    assert weekly(item) is None


def test_756_volume_dashboard_horizon_and_scheduled_demand_match(db):
    c=plan(db)
    vial(db,c)
    h=compare_horizons(db)[0]
    assert h["available"] == pytest.approx(10)
    assert h["unit"] == "mL"
    assert h["horizons"][28]["demand"] == pytest.approx(0.2*28/3)
    scheduled, warnings=build_schedule(db, today=TODAY)
    item=next(x for x in scheduled if x["compound"]=="Synthetic Test C")
    assert item["unit"]=="mL"
    assert item["available"] == pytest.approx(10)
    assert item["demands"][28] is not None
    assert item["flags"][28] in ("Roughly covered","Potential shortfall")


def test_756_scheduled_mixed_concentration_flags_review(db):
    c=plan(db)
    vial(db,c,content=2400,liquid_ml=10)
    vial(db,c,content=2000,liquid_ml=10)
    scheduled,_=build_schedule(db,today=TODAY)
    item=next(x for x in scheduled if x["compound"]=="Synthetic Test C")
    assert item["available"] is None
    assert item["flags"][28]=="Review stock"


def test_756_forecast_template_handles_unknown_stock():
    body=(ROOT/"app/templates/inventory_forecast.html").read_text()
    Environment().parse(body)
    assert "row.available is none" in body
    assert "Concentration unavailable" in body
    assert "Mixed concentrations - review" in body


def test_756_no_database_mutation_on_forecast(db):
    c=plan(db)
    vial(db,c)
    db.commit()
    before=db.scalar(select(func.count()).select_from(Vial))
    row=only_row(db)
    after=db.scalar(select(func.count()).select_from(Vial))
    assert before==after==1
    assert row["available"]>0


def test_756_volume_calculation_is_not_same_as_international_units():
    assert normalized(0.2,"mL")==pytest.approx(0.2)
    assert normalized(200,"uL")==pytest.approx(0.2)
    assert normalized(2,"IU")==pytest.approx(2)
    assert normalized(3,"units") is None  # U-100 marks: withdrawal-only
    assert normalized(5,"bad") is None
