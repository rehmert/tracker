from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from sqlalchemy import MetaData, Table, inspect, insert, select
from datetime import datetime, timezone
import json

from .. import config, services, units as U
from ..attachment_integrity337 import uploaded_transaction, delete_after_commit
from ..templating import render
from fastapi import Request
from ..scoped_db390 import get_scoped_db390
from ..models import Coa, CoaAttachment, CoaDefaultDocument645, CoaRevision, Vial, Compound
from ..coa_test_types646 import COA_TEST_TYPE_GROUPS, COA_CUSTOM_TYPE_SENTINEL

from ..attachment_scope396 import require_attachment_scope396
from ..attachment_files400 import (
    require_attachment_workspace400,
    attachment_directory400,
    attachment_file400,
)

router = APIRouter(
    dependencies=[
        Depends(require_attachment_scope396),
        Depends(require_attachment_workspace400),
    ]
)

COA_STATUSES = ("unreviewed", "verified", "rejected", "needs_review")


def _snapshot(coa: Coa) -> dict:
    keys = ("lab_name", "tested_on", "purity_pct", "endotoxin_pct", "endotoxin_eu_per_vial", "endotoxin_result_kind", "job_id",
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


def _parse_endotoxin645(kind: str, value: str) -> tuple[str, float | None]:
    """Store detection-limit reports separately from real numeric measurements."""
    # Direct legacy unit tests may call FastAPI handlers without passing
    # the newly added Form parameter, leaving its Form default object.
    kind = kind.strip() if isinstance(kind, str) else "lt1"
    value = value.strip() if isinstance(value, str) else ""
    if kind == "lt1":
        if value:
            raise ValueError("Remove the numeric endotoxin entry when '<1 EU/vial' is selected.")
        return "lt1", None
    if kind != "exact":
        raise ValueError("Select either <1 EU/vial or an exact endotoxin value.")
    if not value:
        raise ValueError("Enter the endotoxin result in EU/vial when Exact value is selected.")
    try:
        result = float(value)
    except ValueError as exc:
        raise ValueError("Endotoxin EU/vial must be a number.") from exc
    if not 0 <= result < float("inf"):
        raise ValueError("Endotoxin EU/vial must be finite and nonnegative.")
    return "exact", result


@router.post("/vials/{vid}/coas")
async def upload_coa(vid: int, file: UploadFile | None = File(None), lab_name: str = Form(""),
                     tested_on: str = Form(""), purity_pct: str = Form(""),
                     reported_content: str = Form(""), reported_unit: str = Form("mg"),
                     notes: str = Form(""), endotoxin_eu_per_vial: str = Form(""),
                     job_id: str = Form(""), verify_code: str = Form(""),
                     db: Session = Depends(get_scoped_db390),
                     endotoxin_result_kind: str = Form("lt1")):
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
        endotoxin_kind, endotoxin = _parse_endotoxin645(endotoxin_result_kind, endotoxin_eu_per_vial)
        if file and file.filename:
            stored = await services.save_upload(file, attachment_directory400("coa"))
        else:
            import uuid
            stored = dict(original_name="", stored_name="metadata-" + uuid.uuid4().hex,
                          content_type="", size_bytes=0, sha256="")
    except ValueError as exc:
        return services.flash_redirect(back, err=str(exc))
    with uploaded_transaction(db, stored, attachment_directory400("coa"), services.delete_stored_file):
        fields = dict(lab_name=lab_name.strip(), tested_on=tested, purity_pct=purity,
                      reported_content_value=reported, reported_content_unit=unit,
                      notes=notes.strip(), endotoxin_eu_per_vial=endotoxin,
                      endotoxin_result_kind=endotoxin_kind, job_id=job_id.strip(),
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


def _original_coa_file(coa: Coa):
    if not coa.original_name or not coa.stored_name:
        raise HTTPException(404, "Original COA document not found")
    path = attachment_file400("coa", coa.stored_name)
    if not path.is_file():
        raise HTTPException(404, "Original COA document not found")
    return FileResponse(path, media_type=coa.content_type, filename=coa.original_name,
                        content_disposition_type="inline",
                        headers={"X-Content-Type-Options": "nosniff"})


def _attachment_response(item: CoaAttachment):
    path = attachment_file400("coa", item.stored_name)
    if not path.is_file():
        raise HTTPException(404, "Document file not found")
    return FileResponse(path, media_type=item.content_type, filename=item.original_name,
                        content_disposition_type="inline",
                        headers={"X-Content-Type-Options": "nosniff"})


@router.get("/coas/{cid}/original-file")
def coa_original_file(cid: int, db: Session = Depends(get_scoped_db390)):
    coa = db.get(Coa, cid)
    if coa is None:
        raise HTTPException(404, "COA not found")
    return _original_coa_file(coa)


@router.get("/coas/{cid}/file")
def coa_file(cid: int, db: Session = Depends(get_scoped_db390)):
    """Stable default COA view link used throughout Tracker."""
    coa = db.get(Coa, cid)
    if coa is None:
        raise HTTPException(404, "COA not found")
    preference = db.get(CoaDefaultDocument645, cid)
    if preference is not None:
        item = db.get(CoaAttachment, preference.attachment_id)
        if item is not None and item.coa_id == cid:
            return _attachment_response(item)
    if coa.original_name:
        return _original_coa_file(coa)
    if coa.attachments:
        return _attachment_response(coa.attachments[0])
    raise HTTPException(404, "No COA document uploaded")



def _resolve_attachment_test_type646(test_type: str, custom_test_type: str = "") -> str:
    """Keep historical free-text labels and allow an explicit custom choice."""
    choice = test_type.strip()
    if choice == COA_CUSTOM_TYPE_SENTINEL:
        choice = custom_test_type.strip()
        if not choice:
            raise ValueError("Enter a custom test type or choose a listed type.")
    if len(choice) > 120:
        raise ValueError("Test type is too long.")
    return choice


@router.post("/coas/{cid}/attachments")
async def add_coa_attachments(
    cid: int,
    files: list[UploadFile] = File(...),
    test_type: str = Form(""),
    custom_test_type: str = Form(""),
    db: Session = Depends(get_scoped_db390),
):
    coa = db.get(Coa, cid)
    if coa is None:
        raise HTTPException(404, "COA not found")
    if not 1 <= len(files) <= 20 or not all(f.filename for f in files):
        return services.flash_redirect(f"/coas/{cid}", err="Select 1 to 20 files.")
    try:
        test_type = _resolve_attachment_test_type646(test_type, custom_test_type)
    except ValueError as exc:
        return services.flash_redirect(f"/coas/{cid}", err=str(exc))
    directory = attachment_directory400("coa")
    uploaded = []
    try:
        for file in files:
            uploaded.append(await services.save_upload(file, directory))
        for data in uploaded:
            db.add(CoaAttachment(coa_id=cid, test_type=test_type, **data))
        _revision(db, coa, "attachments_added")
        db.commit()
    except ValueError as exc:
        db.rollback()
        for data in uploaded:
            services.delete_stored_file(data["stored_name"], directory)
        return services.flash_redirect(f"/coas/{cid}", err=str(exc))
    except BaseException:
        db.rollback()
        for data in uploaded:
            services.delete_stored_file(data["stored_name"], directory)
        raise
    return services.flash_redirect(f"/coas/{cid}", msg=f"{len(uploaded)} document(s) added.")


@router.get("/coas/{cid}/attachments/{aid}/file")
def coa_attachment_file(cid: int, aid: int, db: Session = Depends(get_scoped_db390)):
    item = db.get(CoaAttachment, aid)
    if item is None or item.coa_id != cid:
        raise HTTPException(404, "Document not found")
    path = attachment_file400("coa", item.stored_name)
    if not path.is_file():
        raise HTTPException(404, "Document file not found")
    return FileResponse(
        path, media_type=item.content_type, filename=item.original_name,
        content_disposition_type="inline",
        headers={"X-Content-Type-Options": "nosniff"},
    )


@router.post("/coas/{cid}/attachments/{aid}/test-type")
def update_coa_attachment_test_type(
    cid: int, aid: int, test_type: str = Form(""),
    custom_test_type: str = Form(""),
    db: Session = Depends(get_scoped_db390),
):
    coa = db.get(Coa, cid)
    item = db.get(CoaAttachment, aid)
    if coa is None or item is None or item.coa_id != cid:
        raise HTTPException(404, "Document not found")
    try:
        test_type = _resolve_attachment_test_type646(test_type, custom_test_type)
    except ValueError as exc:
        return services.flash_redirect(f"/coas/{cid}", err=str(exc))
    if item.test_type != test_type:
        _revision(db, coa, "attachment_test_type")
        item.test_type = test_type
        db.commit()
    return services.flash_redirect(f"/coas/{cid}", msg="Test type saved.")


@router.post("/coas/{cid}/default-file")
def select_coa_default_file(
    cid: int, document: str = Form(...),
    db: Session = Depends(get_scoped_db390),
):
    coa = db.get(Coa, cid)
    if coa is None:
        raise HTTPException(404, "COA not found")
    preference = db.get(CoaDefaultDocument645, cid)
    if document == "original":
        if not coa.original_name:
            return services.flash_redirect(f"/coas/{cid}", err="No original document exists.")
        if preference is not None:
            _revision(db, coa, "default_document_changed")
            db.delete(preference)
            db.commit()
    elif 1 <= len(document) <= 20 and document.isascii() and document.isdecimal():
        aid = int(document)
        item = db.get(CoaAttachment, aid)
        if item is None or item.coa_id != cid:
            return services.flash_redirect(f"/coas/{cid}", err="Select a document on this COA.")
        if preference is None or preference.attachment_id != aid:
            _revision(db, coa, "default_document_changed")
            if preference is None:
                db.add(CoaDefaultDocument645(coa_id=cid, attachment_id=aid))
            else:
                preference.attachment_id = aid
            db.commit()
    else:
        return services.flash_redirect(f"/coas/{cid}", err="Invalid document selection.")
    return services.flash_redirect(f"/coas/{cid}", msg="Default COA document saved.")


@router.post("/coas/{cid}/attachments/{aid}/delete")
def delete_coa_attachment(cid: int, aid: int, db: Session = Depends(get_scoped_db390)):
    coa = db.get(Coa, cid)
    item = db.get(CoaAttachment, aid)
    if coa is None or item is None or item.coa_id != cid:
        raise HTTPException(404, "Document not found")
    stored_name = item.stored_name
    preference = db.get(CoaDefaultDocument645, cid)
    if preference is not None and preference.attachment_id == aid:
        db.delete(preference)
    _revision(db, coa, "attachment_deleted")
    db.delete(item)
    db.commit()
    delete_after_commit(stored_name, attachment_directory400("coa"), services.delete_stored_file)
    return services.flash_redirect(f"/coas/{cid}", msg="Document removed.")


@router.post("/coas/{cid}/delete")
def delete_coa(cid: int, db: Session = Depends(get_scoped_db390)):
    c = db.get(Coa, cid)
    if c is None:
        raise HTTPException(404, "COA not found")
    vid = c.all_vials[0].id if c.all_vials else None
    stored_name = c.stored_name if c.original_name else None
    extra_stored_names = [attachment.stored_name for attachment in c.attachments]
    for linked in list(c.all_vials):
        if c in linked.linked_coas:
            linked.linked_coas.remove(c)
        if linked.coa_id == cid:
            remaining = [x for x in linked.all_coas if x.id != cid]
            linked.coa_id = remaining[0].id if remaining else None
        if not [x for x in linked.all_coas if x.id != cid]:
            linked.use_coa_content = False
    db.flush()
    preference = db.get(CoaDefaultDocument645, cid)
    if preference is not None:
        db.delete(preference)
    db.delete(c)
    db.commit()
    delete_after_commit(stored_name, attachment_directory400("coa"), services.delete_stored_file)
    for extra_name in extra_stored_names:
        delete_after_commit(extra_name, attachment_directory400("coa"), services.delete_stored_file)
    return services.flash_redirect(f"/vials/{vid}" if vid else "/coas", msg="COA deleted.")


@router.post("/coas/{cid}/assign")
def assign_coa(cid: int, vial_ids: list[int] = Form([]), db: Session = Depends(get_scoped_db390)):
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
def coa_index(request: Request, compound_id: str | None = None, db: Session = Depends(get_scoped_db390)):
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
def coa_new(request: Request, db: Session = Depends(get_scoped_db390)):
    vials = list(db.scalars(select(Vial).order_by(Vial.id)))
    return render(request, "coa_edit.html", coa=None, vials=vials, selected_vial=None)


@router.get("/coas/{cid}")
def coa_detail(cid: int, request: Request, db: Session = Depends(get_scoped_db390)):
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
                  history=history, comparisons=comparisons, statuses=COA_STATUSES,
                  default_attachment_id=(choice.attachment_id if (choice := db.get(CoaDefaultDocument645, cid)) else None),
                  coa_test_type_groups=COA_TEST_TYPE_GROUPS)


@router.post("/coas/new")
async def coa_create(vial_id: int = Form(...), file: UploadFile | None = File(None),
                     lab_name: str = Form(""), tested_on: str = Form(""),
                     purity_pct: str = Form(""), endotoxin_eu_per_vial: str = Form(""),
                     reported_content: str = Form(""), reported_unit: str = Form("mg"),
                     job_id: str = Form(""), verify_code: str = Form(""),
                     notes: str = Form(""), db: Session = Depends(get_scoped_db390),
                     endotoxin_result_kind: str = Form("lt1")):
    # Use the same validation, legacy schema compatibility, and upload logic
    # as the existing vial COA creation endpoint.
    response = await upload_coa(vial_id, file, lab_name, tested_on, purity_pct,
                                reported_content, reported_unit, notes, endotoxin_eu_per_vial,
                                job_id, verify_code, db, endotoxin_result_kind)
    if "err=" not in response.headers.get("location", ""):
        db.expire_all()
        vial = db.get(Vial, vial_id)
        if vial and vial.all_coas:
            return services.flash_redirect(f"/coas/{vial.all_coas[0].id}", msg="COA created.")
    return response


@router.post("/coas/{cid}/edit")
async def coa_edit(cid: int, file: UploadFile | None = File(None),
                   lab_name: str = Form(""), tested_on: str = Form(""),
                   purity_pct: str = Form(""), endotoxin_eu_per_vial: str = Form(""),
                   reported_content: str = Form(""), reported_unit: str = Form("mg"),
                   job_id: str = Form(""), verify_code: str = Form(""),
                   notes: str = Form(""), db: Session = Depends(get_scoped_db390),
                   endotoxin_result_kind: str = Form("lt1")):
    coa = db.get(Coa, cid)
    if coa is None:
        raise HTTPException(404, "COA not found")
    back = f"/coas/{cid}"
    new_file = None
    try:
        purity = _opt_float(purity_pct)
        if purity is not None and not 0 <= purity <= 100:
            raise ValueError("Purity must be between 0 and 100%.")
        endotoxin_kind, endotoxin = _parse_endotoxin645(endotoxin_result_kind, endotoxin_eu_per_vial)
        content = _opt_float(reported_content)
        if content is not None and content <= 0:
            raise ValueError("Reported content must be positive.")
        unit = U.parse_unit(reported_unit).name if content is not None else None
        if content is not None and any(U.parse_unit(v.content_unit).dim != U.parse_unit(unit).dim for v in coa.all_vials):
            raise ValueError("Reported content unit must match linked vials.")
        tested = services.parse_date(tested_on)
        if file and file.filename:
            new_file = await services.save_upload(file, attachment_directory400("coa"))
    except ValueError as exc:
        return services.flash_redirect(back, err=str(exc))
    with uploaded_transaction(db, new_file, attachment_directory400("coa"), services.delete_stored_file):
        old_name = coa.stored_name if coa.original_name else None
        _revision(db, coa, "edit")
        coa.lab_name = lab_name.strip()
        coa.tested_on = tested
        coa.purity_pct = purity
        coa.endotoxin_eu_per_vial = endotoxin
        coa.endotoxin_result_kind = endotoxin_kind
        coa.reported_content_value = content
        coa.reported_content_unit = unit
        coa.job_id = job_id.strip()
        coa.verify_code = verify_code.strip()
        coa.notes = notes.strip()
        if new_file:
            for key, value in new_file.items():
                setattr(coa, key, value)
        db.commit()
    if new_file and old_name:
        delete_after_commit(old_name, attachment_directory400("coa"), services.delete_stored_file)
    return services.flash_redirect(back, msg="COA updated.")


@router.post("/coas/{cid}/unlink/{vid}")
def coa_unlink(cid: int, vid: int, db: Session = Depends(get_scoped_db390)):
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
               db: Session = Depends(get_scoped_db390)):
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
                     db: Session = Depends(get_scoped_db390)):
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
