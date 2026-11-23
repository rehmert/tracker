"""Release 758: read-only mass target and U100 syringe marks on vial labels.

Uses exclusively synthetic local ORM records. Never prints real patient data,
changes protocol dosage, writes administrations or consumes physical stock.
"""
from __future__ import annotations

from datetime import date, timedelta
from types import SimpleNamespace as S
from pathlib import Path

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, select, func
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool
from jinja2 import Environment

from app.db import Base
from app.models import Compound, Protocol, ProtocolItem, Vial, DoseLog
from app.services import vial_views
from app.vial_label_dose758 import (
    active_targets758, resolve_target758, dose_line758,
    validate_label_fit758,
)
from app.vial_labels423 import label_lines, _panel_size, _selected
from app.vial_label_rotation431 import svg_bytes, png_bytes
from app.vial_label_sheets447 import label_panels447
from app.routers import vials as router

ROOT=Path(__file__).resolve().parents[1]


@pytest.fixture
def session():
    engine=create_engine("sqlite://",connect_args={"check_same_thread":False},
                         poolclass=StaticPool)
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        yield db
    engine.dispose()


def stock(db, *, mg=2400, ml=10, mixed=True):
    c=Compound(name="Synthetic Test C", category="testosterone",
               primary_unit="mg")
    db.add(c);db.flush()
    v=Vial(compound_id=c.id,content_value=mg,content_unit="mg",
           volume_ml=ml,status="in_use", label="SIMULATION",
           reconstituted_on=date.today()-timedelta(days=3) if mixed else None,
           beyond_use_on=date.today()+timedelta(days=20))
    db.add(v);db.flush()
    return c,v


def protocol(db, c, *, amount=50, unit="mg", start_days=7,
             active=True, start_week=1, end_week=None):
    p=Protocol(name="Synthetic active mass target",is_active=active,
               start_date=date.today()-timedelta(days=start_days))
    db.add(p);db.flush()
    item=ProtocolItem(protocol_id=p.id,compound_id=c.id,position=0,
                      amount_value=amount,amount_unit=unit,
                      freq_count=3,freq_period="interval",
                      start_week=start_week,end_week=end_week)
    db.add(item);db.flush()
    return p,item


def test_758_target_is_mg_from_only_one_current_active_mass_plan(session):
    c,v=stock(session)
    protocol(session,c)
    assert active_targets758(session,{c.id})=={c.id:[50]}
    assert resolve_target758([50])==(50,"single current active protocol target")
    assert resolve_target758([50],"40")==(
        40,"explicit label target")
    protocol(session,c,amount=75)
    assert active_targets758(session,{c.id})=={c.id:[50,75]}
    assert resolve_target758([50,75])[0] is None


@pytest.mark.parametrize("amount,unit,expected",[
    (50000,"mcg",50),(0.05,"g",50),(50,"mg",50)
])
def test_758_mass_dimensions_convert_to_correct_mg(session,amount,unit,expected):
    c,_=stock(session)
    protocol(session,c,amount=amount,unit=unit)
    assert active_targets758(session,{c.id})=={c.id:[expected]}


def test_758_future_inactive_and_noncurrent_protocols_not_inferred(session):
    c,_=stock(session)
    protocol(session,c,active=False,amount=20)
    protocol(session,c,amount=25,start_days=-3)
    protocol(session,c,amount=30,start_week=9)
    protocol(session,c,amount=40,end_week=1)
    protocol(session,c,amount=0.2,unit="mL")
    assert active_targets758(session,{c.id})=={}


def test_758_240mg_per_ml_and_50mg_target_produce_20833_u100_marks(session):
    c,v=stock(session)
    data=vial_views(session,[v])[v.id]
    dose=dose_line758(data,50)
    assert dose["concentration_mg_ml"]==pytest.approx(240)
    assert dose["target_mg"]==50
    assert dose["withdrawal_ml"]==pytest.approx(50/240)
    assert dose["syringe_units"]==pytest.approx(50/240*100)
    assert dose["line"]=="TARGET:50MG U100:20.833"
    assert "IU" not in dose["line"]


def test_758_target_uses_each_vials_own_actual_concentration(session):
    c,v=stock(session)
    w=Vial(compound_id=c.id,content_value=2500,content_unit="mg",
           volume_ml=10,status="sealed",
           reconstituted_on=date.today(),beyond_use_on=date.today()+timedelta(days=30))
    session.add(w);session.flush()
    views=vial_views(session,[v,w])
    assert dose_line758(views[v.id],50)["line"]=="TARGET:50MG U100:20.833"
    assert dose_line758(views[w.id],50)["line"]=="TARGET:50MG U100:20"


def test_758_no_concentration_wrong_dimension_and_invalid_targets_fail(session):
    c,v=stock(session,ml=None)
    view=vial_views(session,[v])[v.id]
    with pytest.raises(ValueError,match="liquid volume"):
        dose_line758(view,50)
    for target in (0,-10,float("nan"),float("inf"),"garbage"):
        with pytest.raises(ValueError,match="Target dose"):
            dose_line758(view,target)
    u=S(dim="iu",conc_per_ml=1000,remaining_base=5000)
    with pytest.raises(ValueError,match="mass units"):
        dose_line758(u,5)


def test_758_no_overlabeling_when_vial_cannot_supply_target(session):
    c,v=stock(session,mg=10,ml=1)
    vd=vial_views(session,[v])[v.id]
    with pytest.raises(ValueError,match="insufficient"):
        dose_line758(vd,50)


def test_758_printed_target_units_fit_40x20_png_svg(session):
    c,v=stock(session)
    calculation=dose_line758(vial_views(session,[v])[v.id],50)
    rows=label_lines(v,"post",dose_line=calculation["line"],
                     concentration_mg_ml=calculation["concentration_mg_ml"])
    assert "TARGET:50MG U100:20.833" in rows
    assert "240 MG/ML" in rows
    chosen=_selected(rows,*_panel_size("40x20")[:2])
    assert calculation["line"] in chosen
    assert "240 MG/ML" in chosen
    assert any(x.startswith("BUD:") for x in chosen)
    validate_label_fit758(rows,"40x20",0)
    image=svg_bytes(rows,"40x20",0).decode()
    assert calculation["line"] in image
    assert svg_bytes(rows,"40x20",0).startswith(b"<svg")
    assert png_bytes(rows,"40x20",0).startswith(b"\x89PNG\r\n\x1a\n")


def test_758_refuse_small_layout_that_truncates_markings(session):
    c,v=stock(session)
    calculation=dose_line758(vial_views(session,[v])[v.id],50)
    rows=label_lines(v,"post",dose_line=calculation["line"])
    for layout,rotation in (("10x20x4",0),("10x20x4",90),
                            ("40x20",90)):
        with pytest.raises(ValueError,match="cannot print"):
            validate_label_fit758(rows,layout,rotation)


def test_758_pre_mix_labels_remain_without_target(session):
    c,v=stock(session,mixed=False)
    old=label_lines(v,"pre")
    assert "UNRECONSTITUTED" in old
    assert not any(x.startswith("TARGET:") for x in old)
    with pytest.raises(ValueError,match="reconstitution date"):
        label_lines(v,"post")
    dose={"line":"TARGET:50MG U100:20"}
    generated=label_panels447([v],phase="pre",dose_details={v.id:dose})
    assert generated==[old]


def test_758_individual_preview_and_svg_download_use_identical_target(session,monkeypatch):
    c,v=stock(session)
    protocol(session,c)
    monkeypatch.setattr(router,"render",lambda request,template,**kw:kw)
    page=router.vial_labels423(
        v.id, request=object(),phase="post",layout="40x20",
        rotation=0, db=session
    )
    assert page["label_dose_detail"]["line"]=="TARGET:50MG U100:20.833"
    assert page["label_target_mg"]==50
    result=router.vial_labels423_export(
        v.id,phase="post",layout="40x20",rotation=0,
        fmt="svg",download=1,db=session
    )
    assert b"TARGET:50MG U100:20.833" in result.body
    assert result.headers["cache-control"]=="private, no-store"


def test_758_manual_label_target_overrides_ambiguous_protocols(session,monkeypatch):
    c,v=stock(session)
    protocol(session,c,amount=50)
    protocol(session,c,amount=75)
    monkeypatch.setattr(router,"render",lambda request,template,**kw:kw)
    page=router.vial_labels423(
        v.id,request=object(),phase="post",db=session
    )
    assert page["label_target_mg"] is None
    assert page["label_dose_detail"] is None
    assert "Multiple active" in page["label_target_notice"]
    manual=router.vial_labels423_export(
        v.id,phase="post",layout="40x20",fmt="svg",
        target_mg="50",db=session
    )
    assert b"TARGET:50MG U100:20.833" in manual.body
    with pytest.raises(HTTPException) as invalid:
        router.vial_labels423_export(
            v.id,phase="post",target_mg="nan",db=session
        )
    assert invalid.value.status_code==422


def test_758_bulk_auto_uses_each_vial_concentration(session):
    c,v=stock(session)
    w=Vial(compound_id=c.id,content_value=2500,content_unit="mg",
           volume_ml=10,status="sealed",reconstituted_on=date.today())
    session.add(w);session.flush()
    protocol(session,c)
    selected,pages=router._label_job447(
        session,f"{v.id},{w.id}","40x20","auto",0,1
    )
    assert selected==sorted([v.id,w.id])
    lines=[entry for page in pages for entry in page]
    target_lines=[
        next(x for x in row if x.startswith("TARGET:"))
        for row in lines
    ]
    assert target_lines==["TARGET:50MG U100:20.833","TARGET:50MG U100:20"]
    with pytest.raises(HTTPException,match="cannot print"):
        router._label_job447(
            session,f"{v.id},{w.id}","10x20x4","auto",90,1
        )


def test_758_no_dose_log_or_vial_mutation_from_printing(session):
    c,v=stock(session)
    protocol(session,c)
    before=session.scalar(select(func.count()).select_from(DoseLog))
    original=(v.content_value,v.volume_ml,v.status)
    result=router.vial_labels423_export(
        v.id,phase="post",layout="40x20",fmt="png",db=session
    )
    assert result.body.startswith(b"\x89PNG\r\n\x1a\n")
    assert session.scalar(select(func.count()).select_from(DoseLog))==before==0
    assert (v.content_value,v.volume_ml,v.status)==original


def test_758_label_template_preserves_preview_and_download_query():
    template=(ROOT/"app/templates/vial_labels423.html").read_text()
    Environment().parse(template)
    assert 'name="target_mg"' in template
    assert template.count('&amp;target_mg={{ label_target_mg')==3
    assert template.count('&amp;rotation={{ rotation }}')==3
    assert "label-dose-summary758" in template
    assert "U-100 syringe units" in template


def test_758_tiny_target_never_prints_as_zero(session):
    c,v=stock(session,mg=2,ml=1)
    vd=vial_views(session,[v])[v.id]
    with pytest.raises(ValueError,match="too small"):
        dose_line758(vd,0.0000001)


def test_758_mcg_level_label_target_keeps_mass_precision(session):
    c,v=stock(session,mg=2,ml=1)
    vd=vial_views(session,[v])[v.id]
    result=dose_line758(vd,0.005)
    assert result["line"]=="TARGET:0.005MG U100:0.25"


def test_758_small_layout_page_shows_switch_layout_instead_of_422(
        session,monkeypatch):
    c,v=stock(session)
    protocol(session,c)
    monkeypatch.setattr(router,"render",lambda request,template,**kw:kw)
    result=router.vial_labels423(
        v.id,request=object(),phase="post",layout="10x20x4",
        rotation=90,db=session
    )
    assert "cannot print" in result["label_fit_warning"]
    assert result["label_dose_detail"]["line"].startswith("TARGET:50MG")
    html=(ROOT/"app/templates/vial_labels423.html").read_text()
    assert "label-print-fit758" in html
    assert "{% elif label_fit_warning %}" in html
