"""Release 758 four-line post-reconstitution label contracts.

All examples synthetic: preserve mass-vs-concentration semantics, selected
COA, source vendor, BAC-water volume and calculated U-100 markings.
"""
from datetime import date
from pathlib import Path
from types import SimpleNamespace as S

import pytest
from jinja2 import Environment
from app import vial_labels423 as original
from app.vial_label_fourline758 import (
    selected_coa758, four_line_label758, validate_four_line_fit758
)
from app.vial_label_dose758 import dose_line758
from app.vial_label_rotation431 import svg_bytes, png_bytes

ROOT=Path(__file__).resolve().parents[1]


def fake(*,content=10,unit="mg",water=2,vendor="Blackfin Supply",
         coa_amount=11.2,coa_unit="mg",stamp=date(2026,11,23)):
    report=S(id=3,reported_content_value=coa_amount,
             reported_content_unit=coa_unit)
    vial=S(id=9,compound=S(name="Tesamorelin"),
           purchase=S(vendor=vendor) if vendor else None,
           coa=report,all_coas=[report],
           content_value=content,content_unit=unit,
           volume_ml=water,reconstituted_on=stamp,
           form="lyophilized",label="SIMULATED",
           lot="",cap_color="",expires_on=None,beyond_use_on=None)
    return vial, report


def vial_data(mg_ml=6,remaining_mg=10):
    return S(dim="mass",conc_per_ml=mg_ml*1000,
             remaining_base=remaining_mg*1000)


def four(v,report=None,view=None,target=1.4):
    source=view or vial_data()
    detail=dose_line758(source,target) if target is not None else None
    return four_line_label758(v,source,coa=report,detail=detail)


def test_758_exact_four_lines_with_vendor_selected_coa_and_bac():
    v,report=fake()
    lines=four(v,report)
    assert lines==[
        "TESAMORELIN / BLACKFIN SUPPLY",
        "10mg / COA 11.2mg",
        "11/23/26 / BAC2mL / 6mg/mL",
        "1.4mg = 23.333 units",
    ]


def test_758_coa_is_display_only_not_final_concentration():
    v,report=fake()
    lines=four(v,report,view=vial_data(mg_ml=5.5))
    assert lines[1]=="10mg / COA 11.2mg"
    assert lines[2].endswith("/ 5.5mg/mL")
    assert lines[3]=="1.4mg = 25.455 units"


def test_758_coa_selection_not_ambiguous_and_no_unlinked_coa():
    v,primary=fake()
    other=S(id=4,reported_content_value=12.5,reported_content_unit="mg")
    v.all_coas=[primary,other]
    assert selected_coa758(v).id==3
    assert selected_coa758(v,"4").id==4
    assert four(v,selected_coa758(v,"4"))[1]=="10mg / COA 12.5mg"
    v.coa=None
    assert selected_coa758(v) is None
    for bad in ("5","xx","0","-1"):
        with pytest.raises(ValueError,match="COA"):
            selected_coa758(v,bad)


def test_758_without_selected_coa_shows_na():
    v,report=fake()
    lines=four(v,None)
    assert lines[1]=="10mg / COA N/A"
    assert lines[3]=="1.4mg = 23.333 units"


def test_758_no_target_or_concentration_prints_na_not_invented_units():
    v,report=fake()
    bad=S(dim="mass",conc_per_ml=None,remaining_base=10000)
    lines=four_line_label758(v,bad,coa=report,detail=None)
    assert lines[2].endswith("/ N/A mg/mL")
    assert lines[3]=="N/A mg = N/A units"


def test_758_mass_is_different_from_iu_conversions():
    v,report=fake(content=20,unit="IU",coa_amount=21,coa_unit="IU")
    view=S(dim="iu",conc_per_ml=10,remaining_base=20)
    lines=four_line_label758(v,view,coa=report,detail=None)
    assert lines[1]=="20IU / COA 21IU"
    assert lines[2].endswith("/ 10IU/mL")
    assert lines[3]=="N/A mg = N/A units"
    assert "mg/mL" not in lines[2]


def test_758_missing_vendor_water_and_coa_never_guessed():
    v,report=fake(vendor=None,water=None)
    lines=four_line_label758(v,S(dim="mass",conc_per_ml=None,remaining_base=10000),
                             coa=None,detail=None)
    assert " / N/A" in lines[0]
    assert "COA N/A" in lines[1]
    assert "BAC N/A" in lines[2]


def test_758_final_concentration_assigned_from_canonical_vial_not_test_result():
    v,report=fake()
    base=vial_data(mg_ml=5.0)
    detail=dose_line758(base,1.4)
    lines=four_line_label758(v,base,coa=report,detail=detail)
    assert lines[1]=="10mg / COA 11.2mg"
    assert lines[2]=="11/23/26 / BAC2mL / 5mg/mL"
    assert lines[3]=="1.4mg = 28 units"


def test_758_reconstituted_date_is_required():
    v,coa=fake(stamp=None)
    with pytest.raises(ValueError,match="reconstitution date"):
        four(v,coa)


def test_758_print_fit_and_preview_are_complete_svg_png():
    v,coa=fake(vendor="Small Vendor")
    lines=four(v,coa)
    validate_four_line_fit758(lines,"40x20",0)
    svg=svg_bytes(lines,"40x20",0).decode()
    png=png_bytes(lines,"40x20",0)
    assert all(line in svg for line in lines)
    assert png.startswith(b"\x89PNG\r\n\x1a\n")
    assert png!=original.png_bytes(["UNRECONSTITUTED"],"40x20")
    assert len(original._selected(lines,*original._panel_size("40x20")[:2]))==4


@pytest.mark.parametrize("layout,angle",[
    ("10x20x4",90),("10x20x4",0),("30x15x2",0),
    ("40x20",90),("40x20",180)
])
def test_758_unsupported_print_layout_fails_closed(layout,angle):
    v,coa=fake(vendor="S")
    with pytest.raises(ValueError,match="40x20 mm"):
        validate_four_line_fit758(four(v,coa),layout,angle)


def test_758_name_or_vendor_too_long_is_not_silently_truncated():
    v,coa=fake(vendor="An Extremely Long Supplier Company Legal Name")
    with pytest.raises(ValueError,match="cannot print"):
        validate_four_line_fit758(four(v,coa),"40x20",0)


def test_758_pre_mix_label_remains_original():
    v,coa=fake()
    v.reconstituted_on=None
    old=original.label_lines(v,"pre")
    assert "UNRECONSTITUTED" in old
    assert not any("BAC" in row for row in old)
    assert not any("units" in row for row in old)


def test_758_html_exposes_explicit_coa_and_syncs_preview_and_download():
    html=(ROOT/"app/templates/vial_labels423.html").read_text()
    Environment().parse(html)
    assert 'name="coa_id"' in html
    assert html.count('&amp;coa_id={{ label_coa_id')==3
    assert "does not change your protocol" in html
    assert "effective vial concentration" in html


def test_758_sheet_function_preserves_four_lines_per_reconstituted_vial():
    from app.vial_label_sheets447 import label_panels447
    v,coa=fake()
    fourlines=four(v,coa)
    result=label_panels447([v],"post",1,four_line_details={v.id:fourlines})
    assert result==[fourlines]
    assert result[0][-1]=="1.4mg = 23.333 units"
