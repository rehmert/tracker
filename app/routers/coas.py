from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse
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
from ..coa_test_types646 import COA_TEST_TYPE_GROUPS, COA_TEST_TYPE_VALUES, COA_CUSTOM_TYPE_SENTINEL
from ..coa_multitypes651 import decode as decode_types651, from_selection as choose_types651
from ..coa_catalog652 import (
    catalog652, groups652, test_info652, from_selection652,
)

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
        if stored["original_name"]:
            # First document is a regular editable COA attachment from day one.
            db.add(CoaAttachment(coa_id=coa_id, test_type="", job_id=job_id.strip(),
                                 verify_code=verify_code.strip(), **stored))
        v.linked_coas.append(new_coa)
        if v.coa_id is None:
            v.coa_id = coa_id
        db.commit()
    return services.flash_redirect(back, msg="COA uploaded.")


def _legacy_document_attachment650(coa: Coa) -> CoaAttachment | None:
    """Existing root COA file has a compatibility mirror in attachments."""
    if not coa.original_name or not coa.stored_name:
        return None
    return next((a for a in coa.attachments if a.stored_name == coa.stored_name), None)


def _document_rows650(coa: Coa, default_id: int | None, catalog=()) -> list[dict]:
    """Present legacy first files and normal uploads with identical controls.

    No read-path data writes and no requirement to backfill every historical
    original. A legacy root-file row gets an attachment mirror when its test
    type is first edited; both records reference the same physical file.
    """
    mirror = _legacy_document_attachment650(coa)
    rows = []
    if coa.original_name:
        rows.append({
            "key": "original",
            "filename": coa.original_name,
            "test_type": mirror.test_type if mirror else "",
            "job_id": coa.job_id or "",
            "verify_code": coa.verify_code or "",
            **test_info652(mirror.test_type if mirror else "", catalog),
            "size": coa.size_bytes,
            "url": f"/coas/{coa.id}/original-file",
            "delete_id": mirror.id if mirror else 0,
            "default": (default_id is None or (mirror is not None and
                                                default_id == mirror.id)),
        })
    for attachment in coa.attachments:
        if mirror is not None and attachment.id == mirror.id:
            continue
        rows.append({
            "key": str(attachment.id),
            "filename": attachment.original_name,
            "test_type": attachment.test_type or "",
            "job_id": attachment.job_id or "",
            "verify_code": attachment.verify_code or "",
            **test_info652(attachment.test_type, catalog),
            "size": attachment.size_bytes,
            "url": f"/coas/{coa.id}/attachments/{attachment.id}/file",
            "delete_id": attachment.id,
            "default": default_id == attachment.id or (
                default_id is None and not coa.original_name and
                attachment is coa.attachments[0]),
        })
    return rows


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
    if choice.startswith(("~652~", "@652:")):
        raise ValueError("Choose managed catalog types in the multi-test picker.")
    return choice


@router.post("/coas/{cid}/attachments")
async def add_coa_attachments(
    cid: int,
    files: list[UploadFile] = File(...),
    test_type: str = Form(""),
    custom_test_type: str = Form(""),
    test_types: list[str] = Form([]),
    db: Session = Depends(get_scoped_db390),
    job_id: str = Form(""),
    verify_code: str = Form(""),
):
    coa = db.get(Coa, cid)
    if coa is None:
        raise HTTPException(404, "COA not found")
    if not 1 <= len(files) <= 20 or not all(f.filename for f in files):
        return services.flash_redirect(f"/coas/{cid}", err="Select 1 to 20 files.")
    try:
        if test_types or (custom_test_type and not test_type):
            test_type = from_selection652(test_types, custom_test_type, catalog652(db))
        else:
            test_type = _resolve_attachment_test_type646(test_type, custom_test_type)
    except ValueError as exc:
        return services.flash_redirect(f"/coas/{cid}", err=str(exc))
    try:
        job_id = _document_identifier691(job_id, "Task number")
        verify_code = _document_identifier691(verify_code, "Verification number")
    except ValueError as exc:
        return services.flash_redirect(f"/coas/{cid}", err=str(exc))
    if len(files) > 1 and (job_id or verify_code):
        return services.flash_redirect(
            f"/coas/{cid}", err="Upload one document to assign identifiers immediately; "
            "for multiple files, edit each document after uploading."
        )
    directory = attachment_directory400("coa")
    uploaded = []
    try:
        for file in files:
            uploaded.append(await services.save_upload(file, directory))
        for data in uploaded:
            db.add(CoaAttachment(coa_id=cid, test_type=test_type,
                                 job_id=job_id, verify_code=verify_code, **data))
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


def _document_identifier691(value: str, label: str) -> str:
    """Opaque lab-issued text; never infer numbers or fabricate verify URLs."""
    if not isinstance(value, str):
        raise ValueError(f"{label} must be text.")
    text = value.strip()
    if len(text) > 120 or any(ord(char) < 32 or ord(char) == 127 for char in text):
        raise ValueError(f"{label} must be at most 120 printable characters.")
    return text


@router.post("/coas/{cid}/attachments/identifiers")
async def update_coa_document_identifiers691(
    cid: int, request: Request, db: Session = Depends(get_scoped_db390),
):
    """Save identifiers independently for every visible document, atomically.

    Original root-file identifiers remain on Coa for backward compatibility.
    Additional attachments have their own values. No file, lab, test type,
    default-document, or review-status edits occur in this endpoint.
    """
    coa = db.get(Coa, cid)
    if coa is None:
        raise HTTPException(404, "COA not found")
    wants_json = "application/json" in request.headers.get("accept", "").lower()

    def reply(error: str = "", updated: int = 0, status: int = 200):
        if wants_json:
            return JSONResponse(
                {"ok": not bool(error), "error": error, "updated": updated},
                status_code=status,
            )
        response = services.flash_redirect(
            f"/coas/{cid}", err=error,
            msg=f"{updated} document identifier pair(s) saved.",
        )
        response.headers["location"] += "#test-documents"
        return response

    mirror = _legacy_document_attachment650(coa)
    records = {str(item.id): item for item in coa.attachments if item is not mirror}
    if coa.original_name:
        records["original"] = None  # Root COA, mirrored or not.
    if not records:
        return reply("There are no uploaded documents to update.", status=400)
    if len(records) > 250:
        return reply("Too many documents for one update.", status=400)
    form = await request.form()
    expected = {
        f"{field}_{key}"
        for key in records
        for field in ("job_id", "verify_code", "original_job_id", "original_verify_code")
    }
    if set(form.keys()) - {"csrf_token"} != expected:
        return reply("Document list changed. Reload before saving.", status=409)

    proposed = {}
    for key, item in records.items():
        current_job = (coa.job_id or "") if key == "original" else (item.job_id or "")
        current_verify = ((coa.verify_code or "") if key == "original"
                          else (item.verify_code or ""))
        names = (
            f"job_id_{key}", f"verify_code_{key}",
            f"original_job_id_{key}", f"original_verify_code_{key}",
        )
        if any(len(form.getlist(name)) != 1 or not isinstance(form[name], str)
               for name in names):
            return reply("Invalid document identifier form.", status=400)
        old_job, old_verify = form[names[2]], form[names[3]]
        if old_job != current_job or old_verify != current_verify:
            return reply(
                "Document identifiers changed since this page loaded. Reload before saving.",
                status=409,
            )
        try:
            new_job = _document_identifier691(form[names[0]], "Task number")
            new_verify = _document_identifier691(form[names[1]], "Verification number")
        except ValueError as exc:
            return reply(str(exc), status=400)
        proposed[key] = (new_job, new_verify)
    changes = [
        (key, item, proposed[key])
        for key, item in records.items()
        if proposed[key] != (
            (coa.job_id or "", coa.verify_code or "")
            if key == "original" else (item.job_id or "", item.verify_code or "")
        )
    ]
    if changes:
        _revision(db, coa, "document_identifiers_bulk")
        for key, item, (job, verify) in changes:
            if key == "original":
                coa.job_id, coa.verify_code = job, verify
                if mirror is not None:
                    mirror.job_id, mirror.verify_code = job, verify
            else:
                item.job_id, item.verify_code = job, verify
        db.commit()
    return reply(updated=len(changes))


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


@router.post("/coas/{cid}/attachments/test-types")
async def update_coa_attachment_test_types647(
    cid: int, request: Request, db: Session = Depends(get_scoped_db390),
):
    """Validate the entire document editor before one atomic commit.

    The caller posts every currently displayed attachment, including the prior
    value for optimistic concurrency. No partial updates on bad or stale rows.
    """
    coa = db.get(Coa, cid)
    if coa is None:
        raise HTTPException(404, "COA not found")
    wants_json = "application/json" in request.headers.get("accept", "").lower()

    def reply(error: str = "", updated: int = 0, types: dict | None = None,
              status: int = 200):
        if wants_json:
            return JSONResponse(
                {"ok": not bool(error), "error": error, "updated": updated,
                 "types": types or {}},
                status_code=status,
            )
        response = services.flash_redirect(
            f"/coas/{cid}", err=error, msg=f"{updated} test type(s) saved."
        )
        response.headers["location"] += "#test-documents"
        return response

    mirror = _legacy_document_attachment650(coa)
    attachments = {str(item.id): item for item in coa.attachments if item is not mirror}
    if coa.original_name:
        attachments["original"] = mirror  # None = unmirrored legacy file.
    if not attachments:
        return reply("There are no test documents to update.", status=400)
    # The legacy single-choice protocol remains accepted for signed callers.
    # The new browser sends repeated checkbox values and one hidden empty
    # marker per document, so unchecking all tests still submits every row.
    if len(attachments) > 250:
        return reply("Too many test documents for one update.", status=400)
    form = await request.form()
    new_mode = any(name.startswith("test_types_") for name in form.keys())
    names = ("test_types", "custom_test_type", "original_test_type") if new_mode else (
        "test_type", "custom_test_type", "original_test_type"
    )
    expected = {f"{name}_{key}" for key in attachments for name in names}
    submitted = set(form.keys()) - {"csrf_token"}
    if submitted != expected:
        return reply("Document list changed. Reload before saving.", status=409)

    catalog = catalog652(db) if new_mode else ()
    proposed = {}
    for key, attachment in attachments.items():
        previous = form[f"original_test_type_{key}"]
        custom = form[f"custom_test_type_{key}"]
        if (not isinstance(previous, str) or not isinstance(custom, str)
                or len(form.getlist(f"original_test_type_{key}")) != 1
                or len(form.getlist(f"custom_test_type_{key}")) != 1):
            return reply("Invalid test type form.", status=400)
        current = (attachment.test_type or "") if attachment is not None else ""
        if len(previous) > 120 or previous != current:
            return reply("A document changed since you opened the page. Reload before saving.", status=409)
        try:
            if new_mode:
                raw = form.getlist(f"test_types_{key}")
                if (not raw or raw.count("") != 1
                        or not all(isinstance(v, str) for v in raw)):
                    return reply("Invalid multi-test form.", status=400)
                proposed[key] = from_selection652(raw, custom, catalog, previous=current)
            else:
                selected = form[f"test_type_{key}"]
                if (not isinstance(selected, str) or
                        len(form.getlist(f"test_type_{key}")) != 1):
                    return reply("Invalid test type form.", status=400)
                proposed[key] = _resolve_attachment_test_type646(selected, custom)
        except ValueError as exc:
            return reply(str(exc), status=400)

    changed = [(key, attachments[key], label) for key, label in proposed.items()
               if ((attachments[key].test_type or "") if attachments[key] is not None else "") != label]
    if changed:
        _revision(db, coa, "attachment_test_types_bulk")
        for key, item, label in changed:
            if item is None:
                # Copy metadata only; never move, rename or duplicate files.
                assert key == "original" and coa.original_name and coa.stored_name
                db.add(CoaAttachment(
                    coa_id=cid, test_type=label,
                    job_id=coa.job_id or "", verify_code=coa.verify_code or "",
                    original_name=coa.original_name, stored_name=coa.stored_name,
                    content_type=coa.content_type, size_bytes=coa.size_bytes,
                    sha256=coa.sha256,
                ))
            else:
                item.test_type = label
        db.commit()
    return reply(updated=len(changed), types=proposed)


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
            return services.flash_redirect(f"/coas/{cid}", err="Select a document on this COA.")
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
    if coa is None:
        raise HTTPException(404, "Document not found")
    item = db.get(CoaAttachment, aid) if aid else None
    if aid == 0:
        # Legacy root-file row before its first type edit.
        if not coa.original_name or _legacy_document_attachment650(coa) is not None:
            raise HTTPException(404, "Document not found")
        stored_name = coa.stored_name
    elif item is not None and item.coa_id == cid:
        stored_name = item.stored_name
    else:
        raise HTTPException(404, "Document not found")
    preference = db.get(CoaDefaultDocument645, cid)
    if preference is not None and (preference.attachment_id == aid or
                                   (item is not None and stored_name == coa.stored_name)):
        db.delete(preference)
    _revision(db, coa, "attachment_deleted")
    if item is not None:
        db.delete(item)
    if coa.original_name and coa.stored_name == stored_name:
        # Old /original-file URL must not reopen a file removed from this COA.
        import uuid
        coa.original_name = ""
        coa.stored_name = "metadata-" + uuid.uuid4().hex
        coa.content_type = ""
        coa.size_bytes = 0
        coa.sha256 = ""
    db.commit()
    if stored_name:
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
    catalog = catalog652(db)
    return render(request, "coa_edit.html", coa=coa, vials=vials, selected_vial=None,
                  history=history, comparisons=comparisons, statuses=COA_STATUSES,
                  documents=_document_rows650(coa, choice.attachment_id if (choice := db.get(CoaDefaultDocument645, cid)) else None, catalog),
                  coa_test_type_groups=groups652(catalog), coa_test_type_values=COA_TEST_TYPE_VALUES)


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
        mirror = _legacy_document_attachment650(coa)
        if mirror is not None:
            mirror.job_id, mirror.verify_code = coa.job_id, coa.verify_code
        coa.notes = notes.strip()
        if new_file:
            mirror = _legacy_document_attachment650(coa)
            if mirror is not None:
                for key, value in new_file.items():
                    setattr(mirror, key, value)
            else:
                db.add(CoaAttachment(coa_id=cid, test_type="", **new_file))
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
