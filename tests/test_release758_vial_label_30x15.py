"""Release 758: physical 30x15 mm two/four-line label pixel-accurate tests.

Use only synthetic label content. The compact 203 DPI PNG and SVG share
identical glyph placements, so neither can silently crop critical values.
"""
import re
import struct
import xml.etree.ElementTree as ET
import zlib
from datetime import date
from types import SimpleNamespace as S

import pytest

from app import vial_labels423 as original
from app import vial_label_rotation431 as rotated
from app import vial_label_sheets447 as sheets
from app.vial_label_compact758 import geometry758, is_compact758
from app.vial_label_fourline758 import (
    two_line_label758, four_line_label758, validate_four_line_fit758,
)


def sample(production=date(2026, 11, 5), vendor="Blackfin Supply"):
    report=S(id=10, reported_content_value=11.2,
             reported_content_unit="mg")
    vial=S(id=7, compound=S(name="Tesamorelin"),
           purchase=S(vendor=vendor), production_on=production,
           content_value=10, content_unit="mg",
           reconstituted_on=date(2026, 11, 23),
           volume_ml=2, form="lyophilized")
    view=S(dim="mass", conc_per_ml=5000, remaining_base=10000)
    return vial, report, view


def labels(phase="post"):
    vial, report, view = sample()
    if phase == "pre":
        return two_line_label758(vial, coa=report)
    return four_line_label758(
        vial, view, coa=report,
        detail={"target_mg": 1.4, "syringe_units": 28},
    )


def decode_png(png):
    assert png.startswith(b"\x89PNG\r\n\x1a\n")
    width, height = struct.unpack(">II", png[16:24])
    index=8
    stream=bytearray()
    while index<len(png):
        size=struct.unpack_from(">I",png,index)[0]
        kind=png[index+4:index+8]
        payload=png[index+8:index+8+size]
        if kind==b"IDAT":
            stream.extend(payload)
        index+=12+size
        if kind==b"IEND":
            break
    raw=zlib.decompress(stream)
    return width,height,[
        raw[y*(width+1)+1:(y+1)*(width+1)]
        for y in range(height)
    ]


def inner_ink(pixels,w,h,y_offset=0):
    return {
        (x,y-y_offset)
        for y in range(y_offset+2,y_offset+h-2)
        for x in range(2,w-2)
        if pixels[y][x]==0
    }


@pytest.mark.parametrize("phase",["pre","post"])
@pytest.mark.parametrize("layout",["30x15","30x15x2"])
def test_758_compact_30x15_full_lines_in_svg_and_png(phase,layout):
    lines=labels(phase)
    validate_four_line_fit758(lines,layout,0)
    w,h,cols,rows=original._panel_size(layout)
    assert (w,h)==(original.pixels(30),original.pixels(15))
    assert is_compact758(lines,layout)
    png=rotated.png_bytes(lines,layout,0)
    svg=rotated.svg_bytes(lines,layout,0).decode()
    width,height,pixels=decode_png(png)
    assert (width,height)==(w*cols,h*rows)
    assert svg.count('class="tracker-compact-label758"')==rows
    assert all(line in svg for line in lines)
    local=geometry758(lines,w,h,original.FONT)
    expected={(x,y+dy) for x,y in local for dy in (0,1)}
    for row in range(rows):
        assert inner_ink(pixels,w,h,row*h)==expected
    root=ET.fromstring(svg)
    paths=root.findall('.//{http://www.w3.org/2000/svg}path')
    assert len(paths)==rows
    for row,path in enumerate(paths):
        dots={(int(x),int(y)) for x,y in
              re.findall(r"M(\d+) (\d+)h1v2h-1z",path.attrib["d"])}
        assert dots=={(x,y+row*h) for x,y in local}


def test_758_30x15_handles_requested_40_character_first_line():
    lines=labels("post")
    assert lines[0]=="TESAMORELIN / BLACKFIN SUPPLY / 11/05/26"
    assert len(lines[0])==40
    assert lines[2]=="11/23/26 / 2mL BAC / 5mg/mL"
    assert lines[3]=="1.4mg = 28 units"
    validate_four_line_fit758(lines,"30x15",0)


def test_758_two_different_vials_share_one_30x15x2_strip_without_overprint():
    first=labels("post")
    second=labels("post").copy()
    second[0]="TEST PEPTIDE / TEST VENDOR / 11/01/26"
    second[1]="20mg / 21mg"
    second[2]="11/23/26 / 2mL BAC / 10mg/mL"
    second[3]="2mg = 20 units"
    for lines in (first,second):
        validate_four_line_fit758(lines,"30x15x2",0)
    sheet=sheets.svg_sheet447((first,second),"30x15x2",0).decode()
    png=sheets.png_sheet447((first,second),"30x15x2",0)
    w,h,px=decode_png(png)
    assert (w,h)==(original.pixels(30),original.pixels(15)*2)
    assert sheet.count('class="tracker-compact-label758"')==2
    assert sheet.count(first[0])==1 and sheet.count(second[0])==1
    ww,hh=original.pixels(30),original.pixels(15)
    for index,lines in enumerate((first,second)):
        positions=geometry758(lines,ww,hh,original.FONT)
        expected={(x,y+d) for x,y in positions for d in (0,1)}
        assert inner_ink(px,ww,hh,index*hh)==expected


def test_758_30x15_does_not_truncate_overlong_vendor_or_make_up_glyphs():
    lines=labels("pre")
    lines[0]="AN EXTRAORDINARILY LONG COMPOUND / EXTREMELY LONG SUPPLIER / 11/05/26"
    with pytest.raises(ValueError,match="too long"):
        validate_four_line_fit758(lines,"30x15",0)
    bad=labels("pre")
    bad[0]=bad[0].replace("TESAMORELIN","☃")
    with pytest.raises(ValueError,match="Character"):
        validate_four_line_fit758(bad,"30x15",0)


def test_758_30x15_rotated_exact_format_rejected_not_clipped():
    for layout in ("30x15","30x15x2"):
        with pytest.raises(ValueError,match="normal orientation"):
            validate_four_line_fit758(labels("post"),layout,90)


def test_758_legacy_40x20_renderer_unchanged_for_old_content():
    existing=["TEST PEPTIDE","10 MG","VIAL #8","MIX: 2026-11-23"]
    assert not is_compact758(existing,"40x20")
    assert original.png_bytes(existing,"40x20")==rotated.png_bytes(existing,"40x20",0)


def test_758_30x15_is_single_label_in_print_media():
    assert original.LAYOUTS["30x15"]==(30,15,1,1)
    assert original.LAYOUTS["30x15x2"]==(30,15,1,2)



def test_758_30x15_single_vial_http_export_uses_complete_two_four_lines():
    """Real synthetic ORM path, not just the low-level raster helper."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session
    from sqlalchemy.pool import StaticPool
    from app.db import Base
    from app.models import Compound, Purchase, Coa, Vial
    from app.routers import vials as routes

    engine=create_engine("sqlite://",poolclass=StaticPool)
    Base.metadata.create_all(engine)
    try:
        with Session(engine) as db:
            compound=Compound(name="Test Peptide",category="peptide",primary_unit="mg")
            purchase=Purchase(vendor="Test Vendor",
                              purchased_on=date(2026,11,22))
            report=Coa(reported_content_value=11.2,
                       reported_content_unit="mg")
            db.add_all([compound,purchase,report]);db.flush()
            vial=Vial(compound_id=compound.id,purchase_id=purchase.id,
                      coa_id=report.id, content_value=10,content_unit="mg",
                      status="in_use",form="lyophilized",volume_ml=2,
                      production_on=date(2026,11,5),
                      reconstituted_on=date(2026,11,23))
            db.add(vial);db.flush()
            for phase, expected in (
                ("pre",b"10mg / 11.2mg"),
                ("post",b"1.4mg = 28 units"),
            ):
                resp=routes.vial_labels423_export(
                    vial.id,layout="30x15",phase=phase,fmt="svg",
                    rotation=0,coa_id=str(report.id),
                    target_mg="1.4" if phase=="post" else "",
                    db=db
                )
                assert resp.status_code==200
                assert expected in resp.body
                assert b"TEST PEPTIDE / TEST VENDOR / 11/05/26" in resp.body
                assert b'class="tracker-compact-label758"' in resp.body
                assert resp.headers["cache-control"]=="private, no-store"
            png=routes.vial_labels423_export(
                vial.id,layout="30x15",phase="post",fmt="png",
                rotation=0,coa_id=str(report.id),target_mg="1.4",db=db
            )
            assert struct.unpack(">II",png.body[16:24])==(
                original.pixels(30),original.pixels(15))
    finally:
        engine.dispose()
