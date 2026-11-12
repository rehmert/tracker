from datetime import date, datetime
import math
import json
import hashlib

from fastapi.responses import JSONResponse, Response

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from .. import services, units as U
from ..inventory_lock import reserve_inventory_write
from ..scoped_db390 import get_scoped_db390
from ..models import VIAL_STATUSES, DoseLog, Vial, Compound, Supply, SupplyUsage, Coa, PreparationEvent, PreparationSupply, ChangeAudit, BlendComponent, SupplyCategory
from .. import manual_supplies
from ..templating import render
from ..list_queries297 import vial_listing
from ..preparation_reads345 import load_preparations

router = APIRouter()


def _get(db: Session, vid: int) -> Vial:
    v = db.get(Vial, vid)
    if v is None:
        raise HTTPException(404, "Vial not found")
    return v


@router.get("/vials")
def vials_page(request: Request, status: str = "active", compound_id: str | None = None, db: Session = Depends(get_scoped_db390)):
    # Convert compound_id to integer, treating empty strings as None
    compound_id = int(compound_id) if compound_id and compound_id.isdigit() else None

    vials = list(
        db.scalars(
            vial_listing(status,compound_id).options(
                selectinload(Vial.purchase)
            )
        )
    )

    return render(request, "vials.html", vials=vials, views=services.vial_views(db, vials),
                  status=status, statuses=VIAL_STATUSES, compound_id=compound_id, compounds=list(db.scalars(select(Compound).order_by(Compound.name))))




# Release 447: distinct-vial multi-label print sheets, read-only.
# Static /vials/labels paths must precede /vials/{vid}.
def _label_job447(db, ids, layout, phase, rotation, copies):
    from sqlalchemy.orm import joinedload
    from ..vial_label_sheets447 import (
        parse_vial_ids447, validate_options447,
        label_panels447, paginate447,
    )
    try:
        selected_ids = parse_vial_ids447(ids)
        validate_options447(layout, phase, rotation, copies)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    selected = list(db.scalars(
        select(Vial)
        .options(joinedload(Vial.compound))
        .where(Vial.id.in_(selected_ids))
    ))
    lookup = {vial.id: vial for vial in selected}
    if len(lookup) != len(selected_ids) or any(
        ident not in lookup for ident in selected_ids
    ):
        raise HTTPException(404, "One or more selected vials no longer exist")
    ordered = [lookup[ident] for ident in selected_ids]
    try:
        panels = label_panels447(ordered, phase, copies)
        pages = paginate447(panels, layout)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    return selected_ids, pages


@router.get("/vials/labels/sheets")
def vial_label_sheets447_page(
    request: Request,
    ids: str = "",
    layout: str = "10x20x4",
    phase: str = "auto",
    rotation: int = 90,
    copies: int = 1,
    db: Session = Depends(get_scoped_db390),
):
    from markupsafe import Markup
    from ..vial_label_sheets447 import (
        svg_sheet447, physical_size447,
    )

    selected_ids, pages = _label_job447(
        db, ids, layout, phase, rotation, copies,
    )
    width_mm, height_mm = physical_size447(layout)
    sheet_views = [
        {
            "number": index + 1,
            "svg": Markup(svg_sheet447(lines, layout, rotation).decode("utf-8")),
        }
        for index, lines in enumerate(pages)
    ]
    response = render(
        request, "vial_label_sheets447.html",
        selected_ids=",".join(map(str, selected_ids)),
        selected_count=len(selected_ids),
        label_count=sum(map(len, pages)),
        sheets=sheet_views,
        layout=layout, phase=phase,
        rotation=rotation, copies=copies,
        width_mm=width_mm, height_mm=height_mm,
    )
    response.headers["Cache-Control"] = "private, no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    return response


@router.get("/vials/labels/sheets/download")
def vial_label_sheets447_download(
    ids: str = "",
    layout: str = "10x20x4",
    phase: str = "auto",
    rotation: int = 90,
    copies: int = 1,
    fmt: str = "png",
    sheet: int = 0,
    db: Session = Depends(get_scoped_db390),
):
    from ..vial_label_sheets447 import FORMATS
    from ..vial_label_direct450 import direct_download450
    if fmt not in FORMATS or sheet < 0:
        raise HTTPException(422, "Choose SVG or PNG and a valid strip number")
    _, pages = _label_job447(
        db, ids, layout, phase, rotation, copies,
    )
    try:
        result = direct_download450(
            pages, layout, rotation, fmt, sheet,
        )
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc

    media = "image/svg+xml" if fmt == "svg" else "image/png"
    part = f"strip-{sheet:03d}" if sheet else "all-strips"
    return Response(
        content=result, media_type=media,
        headers={
            "Content-Disposition": (
                f'attachment; filename="vial-labels-{layout}-'
                f'{phase}-r{rotation}-{part}.{fmt}"'
            ),
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "private, no-store",
            "Referrer-Policy": "no-referrer",
        },
    )


# TRACKER_BULK_STAGE4

BULK_FIELDS = {
    "status": "choice",
    "lot": "text",
    "label": "text",
    "cap_color": "text",
    "storage_notes": "text",
    "notes": "text",
    "received_on": "date",
    "expires_on": "date",
    "beyond_use_on": "date",
    "first_punctured_on": "date",
    "first_dosed_on": "date",
    "closed_on": "date",
    "use_coa_content": "boolean",
}


def _bulk_parse(form):
    try:
        ids = sorted({int(x) for x in form.getlist("vial_ids")})
    except (TypeError, ValueError):
        raise ValueError("Invalid vial selection.")

    if not ids:
        raise ValueError("Select at least one vial.")

    if len(ids) > 1000:
        raise ValueError("Select at most 1,000 vials.")

    if any(x <= 0 for x in ids):
        raise ValueError("Invalid vial ID.")

    changes = {}

    for field, kind in BULK_FIELDS.items():
        mode = str(form.get("mode_" + field, "keep"))

        if mode not in ("keep", "set", "clear"):
            raise ValueError(f"Invalid action for {field}.")

        if mode == "keep":
            continue

        if mode == "clear":
            if kind in ("choice", "boolean"):
                raise ValueError(f"{field} cannot be cleared.")

            changes[field] = None if kind == "date" else ""
            continue

        raw = str(form.get("value_" + field, "")).strip()

        if kind == "choice":
            if raw not in VIAL_STATUSES:
                raise ValueError("Choose a valid status.")
            changes[field] = raw

        elif kind == "boolean":
            if raw not in ("yes", "no"):
                raise ValueError("Choose Yes or No for COA content.")
            changes[field] = raw == "yes"

        elif kind == "date":
            if not raw:
                raise ValueError(
                    f"Enter a date for {field}, or select Clear."
                )
            changes[field] = services.parse_date(raw)

        else:
            if not raw:
                raise ValueError(
                    f"Enter a value for {field}, or select Clear."
                )
            changes[field] = raw

    if not changes:
        raise ValueError("Choose at least one field to update.")

    return ids, changes


def _bulk_load(db, ids):
    vials = list(
        db.scalars(select(Vial).where(Vial.id.in_(ids)))
    )

    if len(vials) != len(ids):
        raise ValueError(
            "One or more selected vials no longer exist."
        )

    return sorted(vials, key=lambda v: v.id)


def _bulk_validate(vials, changes):
    for vial in vials:
        proposed = {
            field: getattr(vial, field)
            for field in BULK_FIELDS
        }
        proposed.update(changes)

        if (
            proposed["received_on"]
            and proposed["first_punctured_on"]
            and proposed["first_punctured_on"]
                < proposed["received_on"]
        ):
            raise ValueError(
                f"Vial #{vial.id}: first puncture "
                "cannot precede receipt."
            )

        if (
            proposed["first_punctured_on"]
            and proposed["first_dosed_on"]
            and proposed["first_dosed_on"]
                < proposed["first_punctured_on"]
        ):
            raise ValueError(
                f"Vial #{vial.id}: first dose "
                "cannot precede first puncture."
            )

        if proposed["status"] == "sealed" and vial.doses:
            raise ValueError(
                f"Vial #{vial.id} has logged doses "
                "and cannot be marked sealed."
            )


def _bulk_serial(value):
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return value


def _bulk_snapshot(vials, changes):
    """
    Fingerprint the selected vial state and requested changes.

    This is an optimistic concurrency check, not an
    authentication token. Final server-side validation
    remains mandatory.
    """
    state = []

    for vial in vials:
        state.append({
            "id": vial.id,
            "compound_id": vial.compound_id,
            "fields": {
                field: _bulk_serial(getattr(vial, field))
                for field in BULK_FIELDS
            },
            "dose_ids": sorted(d.id for d in vial.doses),
        })

    payload = {
        "vials": state,
        "changes": {
            key: _bulk_serial(value)
            for key, value in sorted(changes.items())
        },
    }

    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")

    return hashlib.sha256(encoded).hexdigest()


def _bulk_rows(vials, changes):
    rows = []

    for vial in vials:
        for field, value in changes.items():
            old = getattr(vial, field)

            rows.append({
                "vial_id": vial.id,
                "compound": vial.compound.name,
                "label": vial.label or f"#{vial.id}",
                "field": field,
                "current": _bulk_serial(old),
                "proposed": _bulk_serial(value),
                "changed": old != value,
            })

    return rows


@router.post("/vials/bulk/preview")
async def bulk_preview_vials(
    request: Request,
    db: Session = Depends(get_scoped_db390),
):
    """
    Read-only preview using current database values.
    Does not reserve an inventory write or commit.
    """
    try:
        form = await request.form()
        ids, changes = _bulk_parse(form)
        vials = _bulk_load(db, ids)
        _bulk_validate(vials, changes)

        return JSONResponse({
            "ok": True,
            "count": len(vials),
            "fields": len(changes),
            "rows": _bulk_rows(vials, changes),
            "snapshot": _bulk_snapshot(vials, changes),
        })

    except (ValueError, TypeError) as exc:
        return JSONResponse(
            {"ok": False, "error": str(exc)},
            status_code=422,
        )



# TRACKER_BULK_STAGE11
@router.post("/vials/bulk/validate-selection")
async def validate_bulk_selection(
    request: Request,
    db: Session = Depends(get_scoped_db390),
):
    """Read-only validation of browser-persisted vial selections."""
    form = await request.form()

    try:
        ids = sorted({
            int(value)
            for value in form.getlist("vial_ids")
        })
    except (ValueError, TypeError):
        return {
            "ok": False,
            "error": "Invalid vial selection.",
        }

    if not ids:
        return {
            "ok": False,
            "error": "Select at least one vial.",
        }

    if len(ids) > 1000:
        return {
            "ok": False,
            "error": "Select at most 1,000 vials.",
        }

    rows = list(db.scalars(
        select(Vial).where(Vial.id.in_(ids))
    ))

    found = {vial.id: vial for vial in rows}

    missing = [
        vial_id for vial_id in ids
        if vial_id not in found
    ]

    current = []

    for vial_id in ids:
        vial = found.get(vial_id)
        if vial is None:
            continue

        current.append({
            "id": str(vial.id),
            "compound": vial.compound.name,
            "label": vial.label or "",
            "status": vial.status,
        })

    return {
        "ok": True,
        "requested": len(ids),
        "found": len(current),
        "missing": missing,
        "current": current,
    }


def _bulk_delete_assessment(db: Session, ids: list[int]):
    vials = list(db.scalars(select(Vial).where(Vial.id.in_(ids)).order_by(Vial.id)))
    result = []
    for vial in vials:
        reasons = []
        if db.scalar(select(DoseLog.id).where(DoseLog.vial_id == vial.id).limit(1)) is not None:
            reasons.append("has logged doses")
        if db.scalar(select(PreparationEvent.id).where(PreparationEvent.vial_id == vial.id).limit(1)) is not None:
            reasons.append("has preparation history")
        if db.scalar(select(BlendComponent.id).where(BlendComponent.source_vial_id == vial.id).limit(1)) is not None:
            reasons.append("is referenced by a blend")
        # Legacy/manual inventory usage can exist without a preparation event.
        # Deleting that vial would leave a dangling foreign-key reference.
        if db.scalar(select(SupplyUsage.id).where(SupplyUsage.vial_id == vial.id).limit(1)) is not None:
            reasons.append("has linked supply usage")
        result.append({
            "id": vial.id,
            "name": f"{vial.compound.name} · {vial.label or ('#' + str(vial.id))}",
            "eligible": not reasons,
            "reason": ", ".join(reasons),
            # Metadata used to detect records changed after preview.
            "status": vial.status,
            "lot": vial.lot,
            "purchase_id": vial.purchase_id,
            "unit_price_cents": vial.unit_price_cents,
            "coa_ids": [coa.id for coa in vial.all_coas],
        })
    missing = sorted(set(ids) - {v.id for v in vials})
    return result, missing


def _bulk_delete_snapshot(ids: list[int], rows: list[dict], missing: list[int]) -> str:
    """Fingerprint exactly the records and eligibility confirmed by the user."""
    payload = json.dumps(
        {"ids": ids, "rows": rows, "missing": missing},
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


@router.post("/vials/bulk/delete-preview")
async def bulk_delete_preview(request: Request, db: Session = Depends(get_scoped_db390)):
    form = await request.form()
    try:
        ids = sorted({int(value) for value in form.getlist("vial_ids")})
        if not ids or len(ids) > 1000 or any(value <= 0 for value in ids):
            raise ValueError
    except (ValueError, TypeError):
        return {"ok": False, "error": "Select between 1 and 1,000 valid vials."}
    rows, missing = _bulk_delete_assessment(db, ids)
    return {
        "ok": True,
        "eligible": [row for row in rows if row["eligible"]],
        "blocked": [row for row in rows if not row["eligible"]],
        "missing": missing,
        "requested": len(ids),
        "snapshot": _bulk_delete_snapshot(ids, rows, missing),
    }


@router.post("/vials/bulk/delete")
async def bulk_delete_vials(request: Request, db: Session = Depends(get_scoped_db390)):
    form = await request.form()
    try:
        ids = sorted({int(value) for value in form.getlist("vial_ids")})
        if not ids or len(ids) > 1000 or any(value <= 0 for value in ids):
            raise ValueError
    except (ValueError, TypeError):
        return services.flash_redirect("/vials", err="Select between 1 and 1,000 valid vials.")
    if not reserve_inventory_write(db):
        return services.flash_redirect("/vials", err="Inventory is busy. Please retry.")
    try:
        rows, missing = _bulk_delete_assessment(db, ids)
        supplied_snapshot = str(form.get("delete_preview_snapshot", "")).strip()
        if not supplied_snapshot or supplied_snapshot != _bulk_delete_snapshot(ids, rows, missing):
            raise ValueError("Deletion preview is missing or stale. Review the selected vials again.")
        eligible_ids = {row["id"] for row in rows if row["eligible"]}
        if not eligible_ids:
            raise ValueError("No selected vials are eligible for deletion. Vials with recorded usage or history must be retained.")
        vials = list(db.scalars(select(Vial).where(Vial.id.in_(eligible_ids)).order_by(Vial.id)))
        for vial in vials:
            db.add(ChangeAudit(
                entity_type="vial",
                entity_id=vial.id,
                action="bulk_delete",
                before_json=json.dumps({
                    "compound": vial.compound.name,
                    "label": vial.label,
                    "lot": vial.lot,
                    "status": vial.status,
                    "purchase_id": vial.purchase_id,
                }),
                after_json="{}",
            ))
            # COAs are shared records; detach this vial without deleting the COA or its file.
            vial.linked_coas.clear()
            vial.coa = None
            db.flush()
            db.delete(vial)
        db.commit()
    except ValueError as exc:
        db.rollback()
        return services.flash_redirect("/vials", err=str(exc))
    except Exception:
        db.rollback()
        raise
    blocked = len(rows) - len(eligible_ids)
    detail = f" {blocked} retained because they have linked usage or history." if blocked else ""
    if missing:
        detail += f" {len(missing)} selected vial(s) were already missing."
    return services.flash_redirect(
        "/vials",
        msg=f"Bulk deletion completed: {len(eligible_ids)} vial(s) deleted.{detail}",
    )


@router.post("/vials/bulk")
async def bulk_update_vials(
    request: Request,
    db: Session = Depends(get_scoped_db390),
):
    """
    Apply validated bulk changes atomically.

    When a preview snapshot is supplied, reject stale
    previews rather than silently applying them.
    """
    form = await request.form()

    try:
        ids, changes = _bulk_parse(form)
    except (ValueError, TypeError) as exc:
        return services.flash_redirect(
            "/vials", err=str(exc)
        )

    if not reserve_inventory_write(db):
        return services.flash_redirect(
            "/vials",
            err="Inventory is busy. Please retry.",
        )

    try:
        vials = _bulk_load(db, ids)
        _bulk_validate(vials, changes)

        supplied_snapshot = str(
            form.get("bulk_preview_snapshot", "")
        ).strip()

        if supplied_snapshot:
            current_snapshot = _bulk_snapshot(
                vials, changes
            )

            if supplied_snapshot != current_snapshot:
                raise ValueError(
                    "Inventory changed since preview. "
                    "Review the selected vials again."
                )

        updated_count = 0

        for vial in vials:
            before = {}
            after = {}

            for field, value in changes.items():
                old = getattr(vial, field)

                if old != value:
                    before[field] = _bulk_serial(old)
                    after[field] = _bulk_serial(value)
                    setattr(vial, field, value)

            if before:
                updated_count += 1

                db.add(ChangeAudit(
                    entity_type="vial",
                    entity_id=vial.id,
                    action="bulk_update",
                    before_json=json.dumps(before),
                    after_json=json.dumps(after),
                ))

        db.commit()

    except (ValueError, TypeError) as exc:
        db.rollback()
        return services.flash_redirect(
            "/vials", err=str(exc)
        )

    except Exception:
        db.rollback()
        raise

    return services.flash_redirect(
        "/vials",
        msg=(
            f"Bulk update completed: {updated_count} "
            f"of {len(vials)} selected vial(s) changed."
        ),
    )


@router.get("/vials/{vid}")
def vial_detail(vid: int, request: Request, db: Session = Depends(get_scoped_db390)):
    v = _get(db, vid)
    vd = services.vial_views(db, [v])[v.id]
    label_base, _ = U.to_base(v.content_value, v.content_unit)
    coa_variance = None
    measurements = []
    for c in v.all_coas:
        if c.reported_content_value is not None and c.reported_content_unit:
            content_base, dim = U.to_base(c.reported_content_value, c.reported_content_unit)
            if dim == U.parse_unit(v.content_unit).dim and content_base > 0:
                measurements.append((c, content_base))
    if measurements:
        average_base = sum(value for _, value in measurements) / len(measurements)
        coa_variance = {"count": len(measurements), "average": U.from_base(average_base, v.content_unit),
                        "unit": v.content_unit, "pct": 100 * (average_base - label_base) / label_base}
    doses = list(db.scalars(select(DoseLog).where(DoseLog.vial_id == vid)
                            .order_by(DoseLog.taken_at.desc())))
    rows = [{"dose": d, "cost": vd.cost_per_base * d.amount_base} for d in doses]
    prep_events, prep_usage = load_preparations(db, vid)

    # Read-only category metadata, matching the Dose log.
    counted_supply_kinds = set(db.scalars(
        select(SupplyCategory.key).where(SupplyCategory.unit == "count")
    ))

    return render(request, "vial_detail.html", v=v, vd=vd, label_base=label_base,
                  coa_variance=coa_variance, rows=rows, statuses=VIAL_STATUSES,
                  extras=vd.landed_cents - v.unit_price_cents, today=date.today().isoformat(),
                  bac_supplies=list(db.scalars(select(Supply).where(Supply.kind == "bac_water", Supply.remaining_qty > 0))),
                  all_coas=list(db.scalars(select(Coa).order_by(Coa.id.desc()))),
                  disposable_supplies=manual_supplies.available(db),
                  counted_supply_kinds=counted_supply_kinds,
                  prep_events=prep_events, prep_usage=prep_usage)


@router.get("/vials/{vid}/labels")
def vial_labels423(
    vid: int,
    request: Request,
    layout: str = "40x20",
    phase: str = "pre",
    rotation: int = 0,
    db: Session = Depends(get_scoped_db390),
):
    from ..vial_labels423 import LAYOUTS
    from ..vial_label_rotation431 import ROTATIONS

    if (
        layout not in LAYOUTS
        or phase not in ("pre", "post")
        or rotation not in ROTATIONS
    ):
        raise HTTPException(422, "Unsupported label selection")

    v = _get(db, vid)
    return render(
        request,
        "vial_labels423.html",
        v=v,
        layout=layout,
        phase=phase,
        rotation=rotation,
    )


@router.get("/vials/{vid}/labels/export")
def vial_labels423_export(
    vid: int,
    layout: str = "40x20",
    phase: str = "pre",
    rotation: int = 0,
    fmt: str = "png",
    download: int = 0,
    db: Session = Depends(get_scoped_db390),
):
    from ..vial_labels423 import (
        LAYOUTS,
        label_lines,
    )
    from ..vial_label_rotation431 import ROTATIONS, svg_bytes, png_bytes

    if (
        layout not in LAYOUTS
        or phase not in ("pre", "post")
        or fmt not in ("svg", "png")
        or rotation not in ROTATIONS
    ):
        raise HTTPException(422, "Unsupported label selection")

    v = _get(db, vid)

    try:
        lines = label_lines(v, phase)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc

    output = (
        svg_bytes(lines, layout, rotation)
        if fmt == "svg"
        else png_bytes(lines, layout, rotation)
    )

    media = "image/svg+xml" if fmt == "svg" else "image/png"
    disposition = "attachment" if download else "inline"

    return Response(
        content=output,
        media_type=media,
        headers={
            "Content-Disposition": (
                f'{disposition}; filename="vial-{vid}-{phase}-{layout}'
                f'{("-r" + str(rotation)) if rotation else ""}.{fmt}"'
            ),
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "private, no-store",
        },
    )


@router.post("/vials/{vid}")
def update_vial(vid: int, label: str = Form(""), lot: str = Form(""), status: str = Form(...),
                content_value: float = Form(...), content_unit: str = Form(...),
                volume_ml: str = Form(""), reconstituted_on: str = Form(""),
                expires_on: str = Form(""), unit_price: str = Form("0"),
                received_on: str = Form(""), first_punctured_on: str = Form(""),
                first_dosed_on: str = Form(""), beyond_use_on: str = Form(""),
                closed_on: str = Form(""), storage_notes: str = Form(""),
                use_coa_content: str = Form(""), notes: str = Form(""), cap_color: str = Form(""),
                db: Session = Depends(get_scoped_db390)):
    if not reserve_inventory_write(db):
        return services.flash_redirect(f"/vials/{vid}", err="Inventory is busy. Please retry.")
    v = _get(db, vid)
    tracked = ("status", "received_on", "first_punctured_on", "first_dosed_on", "beyond_use_on", "closed_on", "storage_notes")
    previous = {key: str(getattr(v, key) or "") for key in tracked}
    back = f"/vials/{vid}"
    try:
        old_dim = U.parse_unit(v.content_unit).dim
        unit = U.parse_unit(content_unit)
        if v.compound.primary_unit == "IU" and unit.dim != "iu":
            raise ValueError("This compound is tracked in IU.")
        if unit.dim != old_dim:
            raise ValueError("Mass vs IU can't be changed on an existing vial. "
                             "Delete it and add a new one.")
        if not math.isfinite(content_value) or content_value <= 0:
            raise ValueError("Content must be a finite number above 0.")
        if status not in VIAL_STATUSES:
            raise ValueError("Unknown status.")
        vol = float(volume_ml) if volume_ml.strip() else None
        if vol is not None and (not math.isfinite(vol) or vol <= 0):
            raise ValueError("Volume must be a finite number above 0.")
        if status == "sealed" and v.doses:
            raise ValueError("A vial with logged doses cannot be marked sealed.")
        v.label, v.lot, v.status = label.strip(), lot.strip(), status
        v.content_value, v.content_unit, v.volume_ml = content_value, unit.name, vol
        v.reconstituted_on = services.parse_date(reconstituted_on)
        v.expires_on = services.parse_date(expires_on)
        for field, raw in (("received_on", received_on), ("first_punctured_on", first_punctured_on),
                           ("first_dosed_on", first_dosed_on), ("beyond_use_on", beyond_use_on),
                           ("closed_on", closed_on)):
            setattr(v, field, services.parse_date(raw))
        if v.first_punctured_on and v.received_on and v.first_punctured_on < v.received_on:
            raise ValueError("First puncture cannot precede receipt.")
        if v.first_dosed_on and v.first_punctured_on and v.first_dosed_on < v.first_punctured_on:
            raise ValueError("First dose cannot precede first puncture.")
        v.storage_notes = storage_notes.strip()
        v.unit_price_cents = services.to_cents(unit_price)
        v.use_coa_content = bool(use_coa_content)
        v.notes = notes.strip()
        v.cap_color = cap_color.strip()
    except ValueError as exc:
        db.rollback()
        return services.flash_redirect(back, err=str(exc))
    current = {key: str(getattr(v, key) or "") for key in tracked}
    if current != previous:
        db.add(ChangeAudit(entity_type="vial", entity_id=vid, action="lifecycle_update",
                           before_json=json.dumps(previous), after_json=json.dumps(current)))
    db.commit()
    return services.flash_redirect(back, msg="Vial updated.")


@router.post("/vials/{vid}/reconstitute")
async def reconstitute(vid: int, request: Request, volume_ml: float = Form(...), supply_id: str = Form(""), db: Session = Depends(get_scoped_db390)):
    if not reserve_inventory_write(db):
        return services.flash_redirect(f"/vials/{vid}", err="Inventory is busy. Please retry.")
    v = _get(db, vid)
    if not math.isfinite(volume_ml) or volume_ml <= 0:
        return services.flash_redirect(f"/vials/{vid}", err="Volume must be more than 0.")
    if v.volume_ml is not None:
        return services.flash_redirect(f"/vials/{vid}", err="Already has a recorded volume. Edit vial details instead.")
    try:
        selected = await manual_supplies.selections(request, db)
    except ValueError as exc:
        return services.flash_redirect(f"/vials/{vid}", err=str(exc))
    if supply_id:
        try:
            sid = int(supply_id)
        except (ValueError, TypeError):
            db.rollback()
            return services.flash_redirect(f"/vials/{vid}", err="Invalid BAC water selection.")
        s = db.get(Supply, sid)
        if not s or s.kind != "bac_water" or s.remaining_qty + 1e-9 < volume_ml:
            return services.flash_redirect(f"/vials/{vid}", err="Insufficient BAC water inventory.")
        if any(item.id == s.id and qty + volume_ml > s.remaining_qty + 1e-9 for item, qty in selected):
            return services.flash_redirect(f"/vials/{vid}", err="Combined BAC water and disposable usage exceeds available stock.")
        s.remaining_qty -= volume_ml
        db.add(SupplyUsage(supply_id=s.id, vial_id=vid, amount=volume_ml))
    event = PreparationEvent(vial_id=vid, kind="reconstitution", notes=f"Added {volume_ml:g} mL")
    db.add(event)
    db.flush()
    for usage in manual_supplies.deduct(db, selected, vial_id=vid):
        db.flush()
        db.add(PreparationSupply(event_id=event.id, usage_id=usage.id))
    v.volume_ml, v.reconstituted_on = volume_ml, date.today()
    if v.status == "sealed":
        v.status = "in_use"
    db.commit()
    return services.flash_redirect(f"/vials/{vid}", msg="Reconstitution recorded.")


@router.post("/vials/{vid}/delete")
def delete_vial(vid: int, db: Session = Depends(get_scoped_db390)):
    if not reserve_inventory_write(db):
        return services.flash_redirect(f"/vials/{vid}", err="Inventory is busy. Please retry.")
    v = _get(db, vid)
    rows, _ = _bulk_delete_assessment(db, [vid])
    if not rows[0]["eligible"]:
        db.rollback()
        return services.flash_redirect(
            f"/vials/{vid}", err="Cannot delete this vial: " + rows[0]["reason"] +
            ". Mark it discarded instead.")
    pid = v.purchase_id
    # A COA may be shared; keep the certificate and file when removing a vial.
    v.linked_coas.clear()
    v.coa = None
    db.flush()
    db.delete(v)
    db.commit()
    return services.flash_redirect(f"/purchases/{pid}" if pid else "/vials", msg="Vial deleted.")


@router.post("/vials/{vid}/filter")
async def record_filtering(vid: int, request: Request, notes: str = Form(""), db: Session = Depends(get_scoped_db390)):
    if not reserve_inventory_write(db):
        return services.flash_redirect(f"/vials/{vid}", err="Inventory is busy. Please retry.")
    _get(db, vid)
    try:
        selected = await manual_supplies.selections(request, db)
    except ValueError as exc:
        return services.flash_redirect(f"/vials/{vid}", err=str(exc))
    if not selected:
        return services.flash_redirect(f"/vials/{vid}", err="Select at least one supply used for filtering.")
    event = PreparationEvent(vial_id=vid, kind="filtering", notes=notes.strip())
    db.add(event)
    db.flush()
    for usage in manual_supplies.deduct(db, selected, vial_id=vid):
        db.flush()
        db.add(PreparationSupply(event_id=event.id, usage_id=usage.id))
    db.commit()
    return services.flash_redirect(f"/vials/{vid}", msg="Filtering supplies recorded.")


@router.get("/vials/{vid}/preparations/{eid}/edit")
def edit_preparation_page(vid: int, eid: int, request: Request, db: Session = Depends(get_scoped_db390)):
    event = db.get(PreparationEvent, eid)
    if not event or event.vial_id != vid: raise HTTPException(404)
    links = list(db.scalars(select(PreparationSupply).where(PreparationSupply.event_id == eid)))
    used = {db.get(SupplyUsage, link.usage_id).supply_id:db.get(SupplyUsage, link.usage_id).amount for link in links}
    return render(request, "preparation_edit.html", event=event, vial=_get(db,vid), supplies=list(db.scalars(select(Supply).order_by(Supply.name))), used=used)


@router.post("/vials/{vid}/preparations/{eid}/edit")
async def edit_preparation(vid: int, eid: int, request: Request, notes: str = Form(""), occurred_at: str = Form(""), db: Session = Depends(get_scoped_db390)):
    if not reserve_inventory_write(db):
        return services.flash_redirect(f"/vials/{vid}", err="Inventory is busy. Please retry.")
    event = db.get(PreparationEvent, eid)
    if not event or event.vial_id != vid: raise HTTPException(404)
    back = f"/vials/{vid}/preparations/{eid}/edit"
    try:
        selected = await manual_supplies.selections(request, db, credits={db.get(SupplyUsage,l.usage_id).supply_id:db.get(SupplyUsage,l.usage_id).amount for l in db.scalars(select(PreparationSupply).where(PreparationSupply.event_id == eid))})
        links = list(db.scalars(select(PreparationSupply).where(PreparationSupply.event_id == eid)))
        previous = [db.get(SupplyUsage, link.usage_id) for link in links]
        original = {}
        for u in previous: original[u.supply_id] = original.get(u.supply_id,0)+u.amount
        for item, qty in selected:
            if qty > item.remaining_qty + original.get(item.id,0) + 1e-9:
                raise ValueError(f"Insufficient {item.name} stock.")
        when = datetime.fromisoformat(occurred_at) if occurred_at else event.occurred_at
        before = {"notes":event.notes,"occurred_at":event.occurred_at.isoformat(),"supplies":original}
        for link, u in zip(links,previous):
            item = db.get(Supply,u.supply_id)
            if item: item.remaining_qty += u.amount
            db.delete(link)
            db.delete(u)
        db.flush()
        for item, qty in selected:
            item.remaining_qty -= qty
            u = SupplyUsage(supply_id=item.id, vial_id=vid, amount=qty)
            db.add(u); db.flush()
            db.add(PreparationSupply(event_id=eid, usage_id=u.id))
        event.notes, event.occurred_at = notes.strip(), when
        db.add(ChangeAudit(entity_type="preparation",entity_id=eid,action="edit",before_json=json.dumps(before),after_json=json.dumps({"notes":event.notes,"occurred_at":when.isoformat(),"supplies":{str(i.id):q for i,q in selected}})))
        db.commit()
    except (ValueError,TypeError) as exc:
        db.rollback()
        return services.flash_redirect(back,err=str(exc))
    return services.flash_redirect(f"/vials/{vid}",msg="Preparation corrected.")


@router.post("/vials/{vid}/preparations/{eid}/delete")
def delete_preparation(vid: int, eid: int, db: Session = Depends(get_scoped_db390)):
    if not reserve_inventory_write(db):
        return services.flash_redirect(f"/vials/{vid}", err="Inventory is busy. Please retry.")
    event = db.get(PreparationEvent,eid)
    if not event or event.vial_id != vid: raise HTTPException(404)
    # Reconstitution records affect vial volume and are not safe to erase after doses.
    if event.kind == "reconstitution":
        return services.flash_redirect(f"/vials/{vid}",err="Reconstitution records cannot be deleted here; correct the vial's recorded volume instead.")
    links = list(db.scalars(select(PreparationSupply).where(PreparationSupply.event_id == eid)))
    old = {}
    usages = []
    for link in links:
        u = db.get(SupplyUsage, link.usage_id)
        if u:
            item = db.get(Supply, u.supply_id)
            if item:
                item.remaining_qty += u.amount
            old[str(u.supply_id)] = old.get(str(u.supply_id), 0) + u.amount
            usages.append(u)
        db.delete(link)
    # Explicitly flush child link removals before removing their referenced
    # usage rows. The ORM does not infer ordering across these separate
    # mapped classes without a declared relationship; SQLite FK enforcement
    # otherwise rejects a DELETE of a still-referenced supply usage.
    db.flush()
    for usage in usages:
        db.delete(usage)
    db.flush()
    db.add(ChangeAudit(entity_type="preparation", entity_id=eid, action="delete",
                       before_json=json.dumps({"kind": event.kind, "supplies": old,
                                               "notes": event.notes})))
    db.delete(event)
    db.commit()
    return services.flash_redirect(f"/vials/{vid}",msg="Preparation removed; supplies restored.")
