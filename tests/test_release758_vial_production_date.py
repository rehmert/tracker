"""Release 758: production-date and exact pre/post NIIMBOT label contracts.

No real patient, product, vendor or clinical values are read. Manufacturing
date must be separately recorded and cannot be inferred from purchase or COA.
"""
from datetime import date
from pathlib import Path
from types import SimpleNamespace as S
import struct

import pytest
from sqlalchemy import create_engine,inspect,select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.db import Base
from app import migrations
from app.models import Compound,Vial,Purchase,Coa
from app import vial_labels423 as label
from app.vial_label_fourline758 import (
    two_line_label758,four_line_label758,selected_coa758,validate_four_line_fit758
)
from app.vial_label_dose758 import dose_line758
from app.services import vial_views
from app.vial_label_rotation431 import svg_bytes,png_bytes
from app.routers import vials as route

ROOT=Path(__file__).resolve().parents[1]


def synthetic(produced=date(2026,11,1),recon=date(2026,11,22),
              vendor="Test Vendor"):
    result=S(id=17,reported_content_value=11.2,reported_content_unit="mg")
    v=S(
        id=44,compound=S(name="Test Peptide"),
        purchase=S(vendor=vendor,purchased_on=date(2026,11,15)),
        production_on=produced,reconstituted_on=recon,
        content_value=10.0,content_unit="mg",volume_ml=2.0,
        form="lyophilized",all_coas=[result],coa=result
    )
    view=S(dim="mass",conc_per_ml=5000,remaining_base=10000)
    return v,result,view


def test_758_unreconstituted_exactly_two_lines_with_manufacture_date():
    v,coa,_=synthetic()
    v.reconstituted_on=None
    assert two_line_label758(v,coa=coa)==[
        "TEST PEPTIDE / TEST VENDOR / 11/01/26",
        "10mg / 11.2mg",
    ]
    assert len(two_line_label758(v,coa=coa))==2


def test_758_reconstituted_exactly_four_lines_with_both_dates():
    v,coa,view=synthetic()
    calculation=dose_line758(view,1.4)
    lines=four_line_label758(v,view,coa=coa,detail=calculation)
    assert lines==[
        "TEST PEPTIDE / TEST VENDOR / 11/01/26",
        "10mg / 11.2mg",
        "11/22/26 / 2mL BAC / 5mg/mL",
        "1.4mg = 28 units",
    ]


def test_758_production_date_unknown_does_not_use_purchase_or_coa_date():
    v,coa,_=synthetic(produced=None)
    coa.tested_on=date(2026,10,31)
    lines=two_line_label758(v,coa=coa)
    assert lines[0]=="TEST PEPTIDE / TEST VENDOR / N/A"
    assert "11/15/26" not in lines[0]
    assert "10/31/26" not in lines[0]


def test_758_selected_tested_content_must_come_from_linked_coa():
    v,coa,_=synthetic()
    extra=S(id=18,reported_content_value=12.1,reported_content_unit="mg")
    v.all_coas=[coa,extra]
    assert two_line_label758(v,selected_coa758(v,"18"))[1]=="10mg / 12.1mg"
    with pytest.raises(ValueError,match="linked"):
        selected_coa758(v,"100")
    assert two_line_label758(v,coa=None)[1]=="10mg / N/A"


@pytest.mark.parametrize("phase",["pre","post"])
def test_758_50x30_complete_label_rendered_png_svg(phase):
    v,coa,view=synthetic()
    items=(two_line_label758(v,coa=coa) if phase=="pre" else
           four_line_label758(v,view,coa=coa,
                              detail=dose_line758(view,1.4)))
    validate_four_line_fit758(items,"50x30",0)
    svg=svg_bytes(items,"50x30",0)
    png=png_bytes(items,"50x30",0)
    assert all(line.encode() in svg for line in items)
    assert png.startswith(b"\x89PNG\r\n\x1a\n")
    assert struct.unpack(">II",png[16:24])==(label.pixels(50),label.pixels(30))
    assert len(label._selected(items,*label._panel_size("50x30")[:2]))==len(items)


def test_758_overlong_40x20_first_line_rejected_not_clipped():
    v,coa,_=synthetic(vendor="A Manufacturer With An Extremely Long Name")
    rows=two_line_label758(v,coa=coa)
    with pytest.raises(ValueError,match="cannot print"):
        validate_four_line_fit758(rows,"40x20",0)


def test_758_new_production_date_is_nullable_additive_migration():
    engine=create_engine("sqlite://",poolclass=StaticPool)
    with engine.begin() as conn:
        conn.exec_driver_sql("CREATE TABLE vials (id INTEGER PRIMARY KEY)")
    try:
        migrations.migrate(engine)
        migrations.migrate(engine)
        columns={c["name"]:c for c in inspect(engine).get_columns("vials")}
        assert "production_on" in columns
        assert columns["production_on"]["nullable"] is True
        with engine.connect() as conn:
            conn.exec_driver_sql("INSERT INTO vials (id) VALUES (1)")
            assert conn.exec_driver_sql(
                "SELECT production_on FROM vials WHERE id=1"
            ).scalar_one() is None
    finally:
        engine.dispose()


def test_758_orm_production_date_persists_independently_of_purchase():
    engine=create_engine("sqlite://",poolclass=StaticPool)
    Base.metadata.create_all(engine)
    try:
        with Session(engine) as db:
            c=Compound(name="Test Peptide",category="peptide",primary_unit="mg")
            p=Purchase(vendor="Test Vendor",purchased_on=date(2026,11,22))
            db.add_all([c,p]);db.flush()
            v=Vial(compound_id=c.id,purchase_id=p.id,
                   content_value=10,content_unit="mg",form="lyophilized",
                   production_on=date(2026,11,1))
            db.add(v);db.commit()
            fresh=db.get(Vial,v.id)
            assert fresh.production_on==date(2026,11,1)
            assert fresh.purchase.purchased_on==date(2026,11,22)
            assert two_line_label758(fresh)==[
                "TEST PEPTIDE / TEST VENDOR / 11/01/26",
                "10mg / N/A",
            ]
    finally:
        engine.dispose()


def test_758_single_vial_route_pre_and_post_render_exact_lines(monkeypatch):
    engine=create_engine("sqlite://",poolclass=StaticPool)
    Base.metadata.create_all(engine)
    try:
        with Session(engine) as db:
            c=Compound(name="Test Peptide",category="peptide",primary_unit="mg")
            p=Purchase(vendor="Test Vendor",purchased_on=date(2026,11,22))
            coa=Coa(reported_content_value=11.2,reported_content_unit="mg")
            db.add_all([c,p,coa]);db.flush()
            v=Vial(compound_id=c.id,purchase_id=p.id,coa_id=coa.id,
                   content_value=10,content_unit="mg",
                   production_on=date(2026,11,1),
                   volume_ml=2,reconstituted_on=date(2026,11,22),
                   form="lyophilized",status="in_use")
            db.add(v);db.flush()
            for phase,needle in (
                ("pre","TEST PEPTIDE / TEST VENDOR / 11/01/26"),
                ("post","1.4mg = 28 units"),
            ):
                result=route.vial_labels423_export(
                    v.id,phase=phase,layout="50x30",rotation=0,
                    fmt="svg",target_mg="1.4" if phase=="post" else "",
                    coa_id=str(coa.id),db=db
                )
                assert needle.encode() in result.body
                assert b"10mg / 11.2mg" in result.body
            # No dose or vial changes from previews/exports
            assert db.get(Vial,v.id).production_on==date(2026,11,1)
    finally:
        engine.dispose()


def test_758_inventory_date_form_fields_match_schema():
    vial=(ROOT/"app/templates/vial_detail.html").read_text()
    purchase=(ROOT/"app/templates/purchase_detail.html").read_text()
    bulk=(ROOT/"app/templates/vials.html").read_text()
    routes=(ROOT/"app/routers/vials.py").read_text()
    purchasing=(ROOT/"app/routers/purchases.py").read_text()
    assert 'name="production_on"' in vial
    assert 'name="production_on"' in purchase
    assert "('production_on','Production date','date')" in bulk
    assert '"production_on": "date"' in routes
    assert '"production_on", "received_on"' in routes
    assert "production_on=manufactured" in purchasing
    assert "purchase.purchased_on" not in (
        ROOT/"app/vial_label_fourline758.py").read_text()


def test_758_unknown_date_placeholder_on_both_types():
    v,coa,view=synthetic(produced=None)
    pre=two_line_label758(v,coa=coa)
    post=four_line_label758(v,view,coa=coa,
                            detail=dose_line758(view,1.4))
    assert pre[0].endswith("/ N/A")
    assert post[0]==pre[0]


def test_758_png_font_has_all_required_lowercase_syringe_terms():
    for char in "mgunits":
        assert char in label.FONT, "No bitmap glyph for " + char
    assert "=" in label.FONT
