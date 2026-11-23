"""Release 758: exact four-line post-reconstitution NIIMBOT labels.

Label claim and one explicitly selected COA are DISPLAYED as contents/vial.
Final mg/mL and syringe marks come from the same effective VialData used by
Tracker's Dose Log. Selecting a COA for display does not change dose math.
"""
from __future__ import annotations

from datetime import date
from math import isfinite
from . import units as U
from .vial_label_dose758 import _short758


def coa_choices758(vial):
    """Deterministic linked COAs: explicit primary takes precedence.

    Multiple linked reports without a primary are ambiguous, so no report is
    silently selected. A single linked report can be displayed.
    """
    reports = list(getattr(vial, "all_coas", []) or [])
    return reports


def selected_coa758(vial, chosen=None):
    reports=coa_choices758(vial)
    if chosen not in (None,""):
        try:
            key=int(chosen)
        except (ValueError,TypeError,OverflowError):
            raise ValueError("Select a linked COA for this vial.")
        if str(key)!=str(chosen) or key<=0:
            raise ValueError("Select a linked COA for this vial.")
        match=next((r for r in reports if r.id==key),None)
        if match is None:
            raise ValueError("Selected COA is not linked to this vial.")
        return match
    primary=getattr(vial,"coa",None)
    if primary is not None and any(r.id==primary.id for r in reports):
        return primary
    return reports[0] if len(reports)==1 else None


def _number758(value, digits=3):
    if value is None:
        return "N/A"
    try:
        v=float(value)
    except (TypeError,ValueError,OverflowError):
        return "N/A"
    if not isfinite(v) or v<=0:
        return "N/A"
    txt=f"{v:.{digits}f}".rstrip("0").rstrip(".")
    return txt if txt!="0" else "N/A"


def _content758(value,unit):
    try:
        number=float(value)
        parsed=U.parse_unit(unit)
        if not isfinite(number) or number<=0:
            return "N/A"
        if parsed.dim=="mass":
            mg=number*parsed.factor/1000
            return _number758(mg,4)+"mg"
        if parsed.dim=="iu":
            return _number758(number*parsed.factor,3)+"IU"
    except (ValueError,TypeError,OverflowError):
        pass
    return "N/A"


def _plain758(value):
    import re,unicodedata
    s=unicodedata.normalize("NFKD",str(value or ""))
    s=s.encode("ascii","ignore").decode("ascii")
    return re.sub(r"\s+"," ",s).strip().upper() or "N/A"


def four_line_label758(vial,view,*,coa=None,detail=None):
    """Exactly four lines; blank data is shown as N/A, never fabricated."""
    stamp=getattr(vial,"reconstituted_on",None)
    if not isinstance(stamp,date):
        raise ValueError("Record the reconstitution date before printing a mixed label.")
    name=_plain758(getattr(getattr(vial,"compound",None),"name",None))
    vendor=_plain758(getattr(getattr(vial,"purchase",None),"vendor",None))
    original=_content758(vial.content_value,vial.content_unit)
    tested=(_content758(coa.reported_content_value,
                        coa.reported_content_unit)
            if coa is not None else "N/A")
    # COA content is explicitly DISPLAY-only. The dose/concentration comes
    # from canonical vial_views (label claim OR allowed COA average).
    dim=view.dim if view is not None else None
    conc=view.conc_per_ml if view is not None else None
    if (conc is None or not isfinite(conc) or conc<=0 or dim not in ("mass","iu")):
        final="N/A "+("IU/mL" if dim=="iu" else "mg/mL")
    else:
        value=conc/1000 if dim=="mass" else conc
        final=_number758(value,3)+("mg/mL" if dim=="mass" else "IU/mL")
    water=getattr(vial,"volume_ml",None)
    if water is not None and (not isfinite(float(water)) or water<=0):
        water=None
    # The reconstitution form records volume_ml as the added BAC-water
    # volume. Solution-form vials have nominal volume but no BAC assertion.
    water_type=("BAC" if getattr(vial,"form","lyophilized")=="lyophilized"
                else "VOL")
    water_number=_number758(water,3)
    water_text=(f"{water_number}mL {water_type}"
                if water_number!="N/A" else f"N/A {water_type}")
    recon=f"{stamp:%m/%d/%y} / {water_text} / {final}"
    if detail is not None and dim=="mass":
        target=_number758(detail["target_mg"],4)
        units=_number758(detail["syringe_units"],3)
        dose=f"{target}mg = {units} units"
    else:
        dose="N/A mg = N/A units"
    return [
        f"{name} / {vendor}",
        f"{original} / {tested}",
        recon,
        dose,
    ]


def validate_four_line_fit758(lines,layout,rotation):
    """Reject truncation in *both* the SVG and the actual PNG glyph path."""
    from . import vial_labels423 as base
    from . import vial_label_rotation431 as rotated
    if len(lines)!=4 or not all(isinstance(s,str) and s for s in lines):
        raise ValueError("Reconstituted labels require four nonempty lines.")
    w,h,_,_=base._panel_size(layout)
    # The 40x20 normal PNG uses the dedicated horizontal glyph condensation.
    # Rotation and other layouts still use legacy 2x horizontal glyphs, which
    # could silently clip a row despite appearing complete in SVG. Fail
    # closed until both render paths support an equivalent compact font.
    if layout != "40x20" or rotation != 0:
        raise ValueError(
            "Four-line reconstituted labels require 40x20 mm with "
            "normal text direction to avoid clipped dose values."
        )
    text_w,text_h=w,h
    chosen=(rotated._selected_rotated(lines,text_w,text_h)
            if rotation else base._selected(lines,w,h))
    # The 4-line PNG uses horizontally condensed glyphs, 2x vertically,
    # on full-size media. At 10mm media the legacy 1x path is retained.
    # Check capacity for the *entire* original line, never a prefix.
    max_glyphs=(text_w-8)//(6 if text_w>=120 else 6)
    if chosen!=lines or len(lines)>max(3,(text_h-10)//17) or any(
        len(s)>max_glyphs for s in lines
    ):
        raise ValueError(
            "The chosen label layout cannot print all four complete lines. "
            "Choose 40x20 mm with normal orientation or shorten the "
            "compound/vendor text; never print truncated dose values."
        )
