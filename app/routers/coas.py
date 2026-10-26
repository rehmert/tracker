from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from sqlalchemy import MetaData, Table, inspect, insert

from .. import config, services, units as U
from ..templating import render
from fastapi import Request
from ..db import get_db
from ..models import Coa, Vial

router = APIRouter()


def _opt_float(text: str) -> float | None:
    text = (text or "").strip()
    return float(text) if text else None


@router.post("/vials/{vid}/coas")
async def upload_coa(vid: int, file: UploadFile | None = File(None), lab_name: str = Form(""),
                     tested_on: str = Form(""), purity_pct: str = Form(""),
                     reported_content: str = Form(""), reported_unit: str = Form("mg"),
                     notes: str = Form(""), endotoxin_pct: str = Form(""),
                     job_id: str = Form(""), verify_code: str = Form(""),
                     db: Session = Depends(get_db)):
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
        endotoxin = _opt_float(endotoxin_pct)
        if endotoxin is not None and not 0 <= endotoxin <= 100:
            raise ValueError("Endotoxin percentage must be 0-100.")
        if file and file.filename:
            stored = await services.save_upload(file)
        else:
            import uuid
            stored = dict(original_name="", stored_name="metadata-" + uuid.uuid4().hex,
                          content_type="", size_bytes=0, sha256="")
    except ValueError as exc:
        return services.flash_redirect(back, err=str(exc))
    fields = dict(lab_name=lab_name.strip(), tested_on=tested, purity_pct=purity,
                  reported_content_value=reported, reported_content_unit=unit,
                  notes=notes.strip(), endotoxin_pct=endotoxin, job_id=job_id.strip(),
                  verify_code=verify_code.strip(), **stored)
    # Legacy databases may still have coas.vial_id (sometimes NOT NULL).
    # The ORM intentionally no longer maps that column, so an ORM INSERT
    # fails on those databases. Supply the legacy owner ID only on INSERT;
    # vials.coa_id remains the authoritative relationship.
    if "vial_id" in {c["name"] for c in inspect(db.connection()).get_columns("coas")}:
        legacy_table = Table("coas", MetaData(), autoload_with=db.connection())
        result = db.execute(insert(legacy_table).values(**fields, vial_id=vid))
        coa_id = result.inserted_primary_key[0]
    else:
        coa = Coa(**fields)
        db.add(coa)
        db.flush()
        coa_id = coa.id
    v.coa_id = coa_id
    db.commit()
    return services.flash_redirect(back, msg="COA uploaded.")


@router.get("/coas/{cid}/file")
def coa_file(cid: int, db: Session = Depends(get_db)):
    c = db.get(Coa, cid)
    path = config.UPLOAD_DIR / c.stored_name if c else None
    if c is None or not c.original_name or not path.exists():
        raise HTTPException(404, "File not found")
    return FileResponse(path, media_type=c.content_type, filename=c.original_name,
                        content_disposition_type="inline",
                        headers={"X-Content-Type-Options": "nosniff"})


@router.post("/coas/{cid}/delete")
def delete_coa(cid: int, db: Session = Depends(get_db)):
    c = db.get(Coa, cid)
    if c is None:
        raise HTTPException(404, "COA not found")
    vid = c.vials[0].id if c.vials else None
    stored_name = c.stored_name if c.original_name else None
    db.delete(c)
    db.commit()
    if stored_name:
        services.delete_stored_file(stored_name)
    return services.flash_redirect(f"/vials/{vid}" if vid else "/coas", msg="COA deleted.")


@router.post("/coas/{cid}/assign")
def assign_coa(cid: int, vial_ids: list[int] = Form([]), db: Session = Depends(get_db)):
    coa = db.get(Coa, cid)
    if not coa: raise HTTPException(404)
    if not vial_ids:
        return services.flash_redirect("/coas", err="Select at least one vial.")
    # A COA may be shared, but all assigned vials must contain the same compound.
    # Preserve the compound of already-linked vials, if any.
    existing = coa.vials
    selected = [db.get(Vial, vid) for vid in set(vial_ids)]
    if any(v is None for v in selected):
        return services.flash_redirect("/coas", err="Unknown vial selected.")
    compound_ids = {v.compound_id for v in existing + selected}
    dimensions = {U.parse_unit(v.content_unit).dim for v in existing + selected}
    if len(compound_ids) > 1 or len(dimensions) > 1:
        return services.flash_redirect("/coas", err="A COA must refer to one compound and unit dimension.")
    for vial in selected:
        vial.coa_id = coa.id
    db.commit()
    return services.flash_redirect("/coas", msg="COA assigned to selected vials.")

@router.get("/coas")
def coa_index(request: Request, compound_id: str | None = None, db: Session = Depends(get_db)):
    # Convert compound_id to integer, treating empty strings as None
    compound_id = int(compound_id) if compound_id and compound_id.isdigit() else None

    from sqlalchemy import select
    from ..models import Compound
    vials = list(db.scalars(select(Vial).order_by(Vial.id)))
    coas = list(db.scalars(select(Coa).order_by(Coa.id.desc())))
    if compound_id is not None:
        vials = [v for v in vials if v.compound_id == compound_id]
        coas = [c for c in coas if any(v.compound_id == compound_id for v in c.vials)]
    return render(request, "coas.html", coas=coas, vials=vials, compound_id=compound_id,
                  compounds=list(db.scalars(select(Compound).order_by(Compound.name))))
