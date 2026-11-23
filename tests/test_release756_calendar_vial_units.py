"""Release 756: synthetic Calendar mg-to-U-100 markings and vial handoff.

All data is generated locally; no user medication, database, or export is used.
"""
from __future__ import annotations
from datetime import date, timedelta
from pathlib import Path
from types import SimpleNamespace as S
from urllib.parse import parse_qs, urlsplit
import html

from jinja2 import Environment, FileSystemLoader
import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.db import Base
from app.models import Compound, Vial, Protocol, ProtocolItem, DoseLog
from app.calendar_vial_math756 import vial_choices756
from app.routers.calendar import _month_events
from app.services import vial_views

ROOT = Path(__file__).resolve().parents[1]


def item(value=50.0, unit="mg", cid=5):
    return S(compound_id=cid, amount_value=value, amount_unit=unit)


def physical(id, *, cid=5, status="in_use", closed=None, expiry=None,
             bud=None, label=""):
    return S(id=id, compound_id=cid, status=status, closed_on=closed,
             expires_on=expiry, beyond_use_on=bud, label=label)


def view(*, mg_ml=240.0, remaining_mg=1000.0, dim="mass"):
    return S(dim=dim, conc_per_ml=mg_ml * 1000 if mg_ml is not None else None,
             remaining_base=remaining_mg * 1000)


def choices(target, vials, views, when=None):
    return vial_choices756(target, when or date.today(), vials, views)


def test_756_three_strengths_same_target_mg_different_syringe_units():
    stock=[physical(1),physical(2),physical(3)]
    details={1:view(mg_ml=200),2:view(mg_ml=240),3:view(mg_ml=250)}
    calculated,warning=choices(item(),stock,details)
    assert warning is None
    assert [c["id"] for c in calculated]==[1,2,3]
    assert {c["id"]:c["syringe_units"] for c in calculated}=={
        1:"25",2:"20.833",3:"20"}
    assert {c["id"]:c["withdrawal_ml"] for c in calculated}=={
        1:"0.25",2:"0.2083",3:"0.2"}
    assert {c["id"]:c["target_mg"] for c in calculated}=={
        1:"50",2:"50",3:"50"}
    assert {c["id"]:c["concentration_mg_ml"] for c in calculated}=={
        1:"200",2:"240",3:"250"}


def test_756_compound_iu_mass_restrictions_and_nonmass_plans():
    stock=[physical(1),physical(2,cid=99)]
    data={1:view(dim="iu"),2:view(mg_ml=100)}
    calculated,notice=choices(item(),stock,data)
    assert calculated==[]
    assert "No eligible vial" in notice
    assert choices(item(value=.2,unit="mL"),stock,data)==([],None)
    assert choices(item(value=2,unit="IU"),stock,data)==([],None)


def test_756_missing_concentration_never_guesses_other_vials():
    stock=[physical(1),physical(2)]
    data={1:view(mg_ml=None),2:view(mg_ml=250)}
    result,notice=choices(item(),stock,data)
    assert [c["id"] for c in result]==[2]
    assert "Some vials" in notice


def test_756_expired_closed_finished_and_wrong_compound_not_selectable():
    today=date.today()
    stock=[
        physical(1,expiry=today-timedelta(days=1)),
        physical(2,bud=today-timedelta(days=1)),
        physical(3,closed=today),
        physical(4,status="finished"),
        physical(5,cid=6),
        physical(6,status="sealed"),
    ]
    data={c.id:view() for c in stock}
    result,_=choices(item(),stock,data,today)
    assert [c["id"] for c in result]==[6]
    future, _ = choices(item(), stock, data, today+timedelta(days=2))
    assert [c["id"] for c in future]==[6]


def test_756_insufficient_stock_and_nonfinite_targets_excluded():
    stock=[physical(1)]
    values={1:view(remaining_mg=20)}
    result,notice=choices(item(),stock,values)
    assert result==[] and "sufficient" in notice
    for amount in (0,-1,float("inf"),float("nan")):
        assert choices(item(value=amount),stock,values)==([],None)


def test_756_u100_markings_not_international_units():
    stock=[physical(1)]
    marks,_=choices(item(value=50),stock,{1:view(mg_ml=240)})
    assert marks[0]["syringe_units"]=="20.833"
    assert marks[0]["withdrawal_ml"]=="0.2083"
    assert marks[0]["target_mg"]=="50"


def test_756_jinja_macro_requires_explicit_vial_selection():
    templates=Environment(loader=FileSystemLoader(str(ROOT/"app/templates")),
                          autoescape=True)
    macro=templates.get_template("_calendar_vial_units756.html")
    stock=[physical(1)]
    calculated,_=choices(item(),stock,{1:view()})
    x=S(vial_choices=calculated,vial_conversion_notice=None,
        compound_id=5,amount_value=50,amount_unit="mg",
        dose="50 mg",dose_time="07:00",name="Synthetic Test C")
    page=macro.render(x=x, scheduled_on=date(2026,11,23))
    assert 'action="/doses"' in page
    assert 'name="vial_id" required' in page
    assert '<option value="" selected>Select vial</option>' in page
    assert 'name="planned_unit" value="mg"' in page
    assert 'name="planned_amount" value="50"' in page
    assert 'value="1"' in page
    assert "240 mg/mL" in page
    assert "20.833 U-100 syringe units" in page
    assert "Review selected vial in Dose Log" in page
    # The selection is a GET-only preview, never a dose-creating POST.
    assert 'method="get"' in page
    assert "method=\"post\"" not in page


def test_756_calendar_template_contains_both_vial_pickers_and_no_auto_pick():
    source=(ROOT/"app/templates/calendar.html").read_text()
    assert source.count('_calendar_vial_units756.html')==2
    assert 'tracker-calendar-vial756.js' in source
    assert "Log this dose" in source
    assert "Choose vial first" in source
    assert 'data-calendar-vial-output' in (
        ROOT/"app/templates/_calendar_vial_units756.html").read_text()


def test_756_real_calendar_generates_distinct_vial_calculations():
    engine=create_engine("sqlite://",connect_args={"check_same_thread":False},
                         poolclass=StaticPool)
    Base.metadata.create_all(engine)
    now=date.today().replace(day=1)
    try:
        with Session(engine) as db:
            c=Compound(name="Synthetic calendar testosterone",category="testosterone",
                       primary_unit="mg")
            db.add(c);db.flush()
            protocol=Protocol(name="Synthetic calendar protocol",
                              is_active=True,start_date=now)
            db.add(protocol);db.flush()
            db.add(ProtocolItem(protocol_id=protocol.id,
                                compound_id=c.id,amount_value=50,amount_unit="mg",
                                freq_count=3,freq_period="interval",
                                position=0,start_week=1))
            first=Vial(compound_id=c.id, content_value=2400,
                       content_unit="mg",volume_ml=10,
                       status="in_use")
            second=Vial(compound_id=c.id, content_value=2500,
                        content_unit="mg",volume_ml=10,
                        status="sealed")
            db.add_all([first,second]);db.flush()
            before=db.scalar(select(func.count()).select_from(DoseLog))
            start,end,events,missing=_month_events(now,db)
            assert not missing
            planned=next(e for day in events.values() for e in day
                         if e.get("compound_id")==c.id and "vial_choices" in e)
            assert planned["amount_unit"]=="mg"
            assert {v["id"]:v["syringe_units"]
                    for v in planned["vial_choices"]}=={
                        first.id:"20.833",second.id:"20"}
            assert db.scalar(select(func.count()).select_from(DoseLog))==before==0
    finally:
        engine.dispose()


def test_756_regression_live_dose_preview_preserves_mass_authority():
    code=(ROOT/"app/routers/doses.py").read_text()
    assert 'U.amount_to_vial_base(value, unit, vd.dim, vd.conc_per_ml)' in code
    assert 'marks=U.ml_to_syringe_units(draw)' in code
    # No change to the existing signed Dose Log submission path.
    assert '@router.post("/doses")' in code
