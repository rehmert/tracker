from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from .. import config, services, units as U
from ..db import get_db
from ..models import Coa, Vial

router = APIRouter()


def _opt_float(text: str) -> float | None:
    text = (text or "").strip()
    return float(text) if text else None


@router.post("/vials/{vid}/coas")
async def upload_coa(vid: int, file: UploadFile = File(...), lab_name: str = Form(""),
                     tested_on: str = Form(""), purity_pct: str = Form(""),
                     reported_content: str = Form(""), reported_unit: str = Form("mg"),
                     notes: str = Form(""), db: Session = Depends(get_db)):
    v = db.get(Vial, vid)
    if v is None:
        raise HTTPException(404, "Vial not found")
    back = f"/vials/{vid}"
    stored = None
    try:
        purity = _opt_float(purity_pct)
        if purity is not None and not 0 <= purity <= 100:
            raise ValueError("Purity must be between 0 and 100 %.")
        reported = _opt_float(reported_content)
        unit = None
        if reported is not None:
            if reported <= 0:
                raise ValueError("Reported content must be above 0.")
            u = U.parse_unit(reported_unit)
            if u.dim != U.parse_unit(v.content_unit).dim:
                raise ValueError("The COA's unit must match the vial's (mass vs IU).")
            unit = u.name
        tested = services.parse_date(tested_on)
        stored = await services.save_upload(file)
    except ValueError as exc:
        return services.flash_redirect(back, err=str(exc))
    db.add(Coa(vial_id=vid, lab_name=lab_name.strip(), tested_on=tested, purity_pct=purity,
               reported_content_value=reported, reported_content_unit=unit,
               notes=notes.strip(), **stored))
    db.commit()
    return services.flash_redirect(back, msg="COA uploaded.")


@router.get("/coas/{cid}/file")
def coa_file(cid: int, db: Session = Depends(get_db)):
    c = db.get(Coa, cid)
    path = config.UPLOAD_DIR / c.stored_name if c else None
    if c is None or not path.exists():
        raise HTTPException(404, "File not found")
    return FileResponse(path, media_type=c.content_type, filename=c.original_name,
                        content_disposition_type="inline",
                        headers={"X-Content-Type-Options": "nosniff"})


@router.post("/coas/{cid}/delete")
def delete_coa(cid: int, db: Session = Depends(get_db)):
    c = db.get(Coa, cid)
    if c is None:
        raise HTTPException(404, "COA not found")
    vid = c.vial_id
    services.delete_stored_file(c.stored_name)
    db.delete(c)
    db.commit()
    return services.flash_redirect(f"/vials/{vid}", msg="COA deleted.")
