from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from sqlalchemy import MetaData, Table, inspect, insert, select
from datetime import datetime, timezone
import json

from .. import config, services, units as U
from ..templating import render
from fastapi import Request
from ..db import get_db
from ..models import Coa, CoaRevision, Vial, Compound

router = APIRouter()

COA_STATUSES = ("unreviewed", "verified", "rejected", "needs_review")


def _snapshot(coa: Coa) -> dict:
    keys = ("lab_name", "tested_on", "purity_pct", "endotoxin_pct", "job_id",
            "verify_code", "reported_content_value", "reported_content_unit", "notes",
            "original_name", "sha256", "verification_status", "verification_notes", "verified_at")
    return {key: (value.isoformat() if hasattr(value := getattr(coa, key), "isoformat") else value)
            for key in keys}


def _revision(db: Session, coa: Coa, event: str) -> None:
    db.add(CoaRevision(coa_id=coa.id, event=event,
                       snapshot_json=json.dumps(_snapshot(coa), sort_keys=True)))




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
    new_coa = db.get(Coa, coa_id)
    v.linked_coas.append(new_coa)
    if v.coa_id is None:
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
    vid = c.all_vials[0].id if c.all_vials else None
    stored_name = c.stored_name if c.original_name else None
    for linked in list(c.all_vials):
        if c in linked.linked_coas:
            linked.linked_coas.remove(c)
        if linked.coa_id == cid:
            remaining = [x for x in linked.all_coas if x.id != cid]
            linked.coa_id = remaining[0].id if remaining else None
        if not [x for x in linked.all_coas if x.id != cid]:
            linked.use_coa_content = False
    db.flush()
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
        return services.flash_redirect(f"/coas/{cid}", err="Select at least one vial.")
    # A COA may be shared, but all assigned vials must contain the same compound.
    # Preserve the compound of already-linked vials, if any.
    existing = coa.all_vials
    selected = [db.get(Vial, vid) for vid in set(vial_ids)]
    if any(v is None for v in selected):
        return services.flash_redirect("/coas", err="Unknown vial selected.")
    compound_ids = {v.compound_id for v in existing + selected}
    dimensions = {U.parse_unit(v.content_unit).dim for v in existing + selected}
    if len(compound_ids) > 1 or len(dimensions) > 1:
        return services.flash_redirect("/coas", err="A COA must refer to one compound and unit dimension.")
    for vial in selected:
        if coa not in vial.linked_coas:
            vial.linked_coas.append(coa)
        if vial.coa_id is None:
            vial.coa_id = coa.id
    db.commit()
    return services.flash_redirect(f"/coas/{cid}", msg="COA assigned to selected vials.")

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
        coas = [c for c in coas if any(v.compound_id == compound_id for v in c.all_vials)]
    return render(request, "coas.html", coas=coas, vials=vials, compound_id=compound_id,
                  compounds=list(db.scalars(select(Compound).order_by(Compound.name))))


@router.get("/coas/new")
def coa_new(request: Request, db: Session = Depends(get_db)):
    vials = list(db.scalars(select(Vial).order_by(Vial.id)))
    return render(request, "coa_edit.html", coa=None, vials=vials, selected_vial=None)


@router.get("/coas/{cid}")
def coa_detail(cid: int, request: Request, db: Session = Depends(get_db)):
    coa = db.get(Coa, cid)
    if coa is None:
        raise HTTPException(404, "COA not found")
    vials = list(db.scalars(select(Vial).order_by(Vial.id)))
    history = list(db.scalars(select(CoaRevision).where(CoaRevision.coa_id == cid)
                              .order_by(CoaRevision.id.desc())))
    # Same-compound / same-lot comparisons include independent certificates.
    lot_keys = {(v.compound_id, v.lot.strip().casefold()) for v in coa.all_vials if v.lot.strip()}
    candidates = list(db.scalars(select(Coa).where(Coa.id != cid)))
    comparisons = [c for c in candidates if
                   (coa.job_id and c.job_id and coa.job_id.strip().casefold() == c.job_id.strip().casefold())
                   or any((v.compound_id, v.lot.strip().casefold()) in lot_keys
                          for v in c.all_vials if v.lot.strip())]
    comparisons.sort(key=lambda c: (c.tested_on is not None, c.tested_on, c.id), reverse=True)
    return render(request, "coa_edit.html", coa=coa, vials=vials, selected_vial=None,
                  history=history, comparisons=comparisons, statuses=COA_STATUSES)


@router.post("/coas/new")
async def coa_create(vial_id: int = Form(...), file: UploadFile | None = File(None),
                     lab_name: str = Form(""), tested_on: str = Form(""),
                     purity_pct: str = Form(""), endotoxin_pct: str = Form(""),
                     reported_content: str = Form(""), reported_unit: str = Form("mg"),
                     job_id: str = Form(""), verify_code: str = Form(""),
                     notes: str = Form(""), db: Session = Depends(get_db)):
    # Use the same validation, legacy schema compatibility, and upload logic
    # as the existing vial COA creation endpoint.
    response = await upload_coa(vial_id, file, lab_name, tested_on, purity_pct,
                                reported_content, reported_unit, notes, endotoxin_pct,
                                job_id, verify_code, db)
    if "err=" not in response.headers.get("location", ""):
        db.expire_all()
        vial = db.get(Vial, vial_id)
        if vial and vial.all_coas:
            return services.flash_redirect(f"/coas/{vial.all_coas[0].id}", msg="COA created.")
    return response


@router.post("/coas/{cid}/edit")
async def coa_edit(cid: int, file: UploadFile | None = File(None),
                   lab_name: str = Form(""), tested_on: str = Form(""),
                   purity_pct: str = Form(""), endotoxin_pct: str = Form(""),
                   reported_content: str = Form(""), reported_unit: str = Form("mg"),
                   job_id: str = Form(""), verify_code: str = Form(""),
                   notes: str = Form(""), db: Session = Depends(get_db)):
    coa = db.get(Coa, cid)
    if coa is None:
        raise HTTPException(404, "COA not found")
    back = f"/coas/{cid}"
    new_file = None
    try:
        purity = _opt_float(purity_pct)
        if purity is not None and not 0 <= purity <= 100:
            raise ValueError("Purity must be between 0 and 100%.")
        endotoxin = _opt_float(endotoxin_pct)
        if endotoxin is not None and not 0 <= endotoxin <= 100:
            raise ValueError("Endotoxin must be between 0 and 100%.")
        content = _opt_float(reported_content)
        if content is not None and content <= 0:
            raise ValueError("Reported content must be positive.")
        unit = U.parse_unit(reported_unit).name if content is not None else None
        if content is not None and any(U.parse_unit(v.content_unit).dim != U.parse_unit(unit).dim for v in coa.all_vials):
            raise ValueError("Reported content unit must match linked vials.")
        tested = services.parse_date(tested_on)
        if file and file.filename:
            new_file = await services.save_upload(file)
    except ValueError as exc:
        return services.flash_redirect(back, err=str(exc))
    old_name = coa.stored_name if coa.original_name else None
    _revision(db, coa, "edit")
    coa.lab_name = lab_name.strip()
    coa.tested_on = tested
    coa.purity_pct = purity
    coa.endotoxin_pct = endotoxin
    coa.reported_content_value = content
    coa.reported_content_unit = unit
    coa.job_id = job_id.strip()
    coa.verify_code = verify_code.strip()
    coa.notes = notes.strip()
    if new_file:
        for key, value in new_file.items():
            setattr(coa, key, value)
    try:
        db.commit()
    except Exception:
        db.rollback()
        if new_file:
            services.delete_stored_file(new_file["stored_name"])
        raise
    if new_file and old_name:
        services.delete_stored_file(old_name)
    return services.flash_redirect(back, msg="COA updated.")


@router.post("/coas/{cid}/unlink/{vid}")
def coa_unlink(cid: int, vid: int, db: Session = Depends(get_db)):
    vial = db.get(Vial, vid)
    if vial is None or cid not in [c.id for c in vial.all_coas]:
        raise HTTPException(404, "COA assignment not found")
    coa = db.get(Coa, cid)
    if coa in vial.linked_coas:
        vial.linked_coas.remove(coa)
    if vial.coa_id == cid:
        remaining = [c for c in vial.all_coas if c.id != cid]
        vial.coa_id = remaining[0].id if remaining else None
    if not [c for c in vial.all_coas if c.id != cid]:
        vial.use_coa_content = False
    db.commit()
    return services.flash_redirect(f"/coas/{cid}", msg="Vial unlinked from COA.")


@router.post("/coas/{cid}/verify")
def coa_verify(cid: int, status: str = Form(...), verification_notes: str = Form(""),
               db: Session = Depends(get_db)):
    coa = db.get(Coa, cid)
    if coa is None:
        raise HTTPException(404, "COA not found")
    if status not in COA_STATUSES:
        return services.flash_redirect(f"/coas/{cid}", err="Invalid verification status.")
    if len(verification_notes) > 2000:
        return services.flash_redirect(f"/coas/{cid}", err="Verification notes are too long.")
    _revision(db, coa, "verification")
    coa.verification_status = status
    coa.verification_notes = verification_notes.strip()
    coa.verified_at = datetime.now(timezone.utc).replace(tzinfo=None) if status == "verified" else None
    db.commit()
    return services.flash_redirect(f"/coas/{cid}", msg="Verification status saved.")


@router.post("/vials/{vid}/coas/assign-group")
def assign_group_coa(vid: int, coa_id: int = Form(...), scope: str = Form("vial"),
                     db: Session = Depends(get_db)):
    vial = db.get(Vial, vid)
    coa = db.get(Coa, coa_id)
    if not vial or not coa:
        raise HTTPException(404, "Vial or COA not found")
    if scope not in ("vial", "half", "kit"):
        raise HTTPException(400, "Invalid scope")
    group = [vial]
    if scope != "vial":
        if not vial.kit_ref or vial.purchase_id is None:
            return services.flash_redirect(f"/vials/{vid}", err="This vial has no identifiable kit group.")
        group = list(db.scalars(select(Vial).where(
            Vial.purchase_id == vial.purchase_id, Vial.kit_ref == vial.kit_ref,
            Vial.compound_id == vial.compound_id).order_by(Vial.id)))
        if scope == "half":
            split = (len(group) + 1) // 2
            position = next(i for i, v in enumerate(group) if v.id == vid)
            group = group[:split] if position < split else group[split:]
    existing = coa.all_vials
    if any(v.compound_id != vial.compound_id or
           U.parse_unit(v.content_unit).dim != U.parse_unit(vial.content_unit).dim
           for v in existing + group):
        return services.flash_redirect(f"/vials/{vid}", err="COA compound or unit does not match selected vials.")
    for target in group:
        if coa not in target.linked_coas:
            target.linked_coas.append(coa)
        if target.coa_id is None:
            target.coa_id = coa.id
    db.commit()
    return services.flash_redirect(f"/vials/{vid}", msg=f"COA linked to {len(group)} vial(s).")
