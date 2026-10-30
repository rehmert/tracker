from ..inventory_lock import reserve_inventory_write
from fastapi import APIRouter, Depends, Form, Request, Query
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .. import services, units as U
from ..db import get_db
from ..models import CATEGORIES, Compound, ProtocolItem, Vial, page_compounds
from ..templating import render

router = APIRouter()


@router.get("/compounds")
def compounds_page(request: Request, q: str = Query("", max_length=120),
                   category_filter: str = Query(""), sort: str = Query("name"),
                   direction: str = Query("asc"), db: Session = Depends(get_db)):
    """Search and sort on the server, with an allowlist for ordering."""
    q = q.strip()
    if category_filter not in CATEGORIES:
        category_filter = ""
    sort_columns = {"name": Compound.name, "category": Compound.category,
                    "unit": Compound.primary_unit, "id": Compound.id}
    if sort not in sort_columns:
        sort = "name"
    if direction not in ("asc", "desc"):
        direction = "asc"
    order = sort_columns[sort].desc() if direction == "desc" else sort_columns[sort].asc()
    stmt = select(Compound)
    if q:
        stmt = stmt.where(Compound.name.ilike(f"%{q}%"))
    if category_filter:
        stmt = stmt.where(Compound.category == category_filter)
    compounds = list(db.scalars(stmt.order_by(order, Compound.id.asc())))
    notes = dict(db.execute(select(page_compounds.c.compound_id, func.count())
                            .group_by(page_compounds.c.compound_id)).all())
    return render(request, "compounds.html", compounds=compounds, notes=notes,
                  refs=services.compound_refs(db), categories=CATEGORIES,
                  q=q, category_filter=category_filter, sort=sort, direction=direction)


@router.post("/compounds")
def create_compound(name: str = Form(...), category: str = Form("peptide"),
                    notes: str = Form(""), primary_unit: str = Form("mg"), db: Session = Depends(get_db)):
    if not reserve_inventory_write(db):
        return services.flash_redirect("/compounds", err="Database is busy. Please retry.")
    name = name.strip()
    if not name:
        return services.flash_redirect("/compounds", err="Give the compound a name.")
    if category not in CATEGORIES:
        category = "other"
    if db.scalar(select(Compound).where(func.lower(Compound.name) == name.lower())):
        return services.flash_redirect("/compounds", err=f"'{name}' already exists.")
    if primary_unit not in U.CONTENT_UNITS:
        return services.flash_redirect("/compounds", err="Choose a valid content unit.")
    if name.casefold() in ("somatropin", "somatropin (hgh)", "hgh (somatropin)"):
        primary_unit = "IU"
    db.add(Compound(name=name, category=category, notes=notes.strip(), primary_unit=primary_unit))
    db.commit()
    return services.flash_redirect("/compounds", msg=f"Added {name}.")


@router.post("/compounds/{cid}/delete")
def delete_compound(cid: int, db: Session = Depends(get_db)):
    if not reserve_inventory_write(db):
        return services.flash_redirect("/compounds", err="Database is busy. Please retry.")
    c = db.get(Compound, cid)
    if c is None:
        return services.flash_redirect("/compounds", err="Compound not found.")
    in_use = db.scalar(select(func.count()).select_from(Vial).where(Vial.compound_id == cid)) \
        or db.scalar(select(func.count()).select_from(ProtocolItem)
                     .where(ProtocolItem.compound_id == cid))
    if in_use:
        return services.flash_redirect(
            "/compounds", err=f"{c.name} is used by vials or protocols, so it can't be deleted.")
    db.delete(c)
    db.commit()
    return services.flash_redirect("/compounds", msg=f"Deleted {c.name}.")


@router.get("/compounds/{cid}/edit")
def edit_compound_page(cid: int, request: Request, db: Session = Depends(get_db)):
    compound = db.get(Compound, cid)
    if compound is None:
        return services.flash_redirect("/compounds", err="Compound not found.")
    has_vials = bool(db.scalar(select(func.count()).select_from(Vial).where(Vial.compound_id == cid)))
    return render(request, "compound_edit.html", compound=compound,
                  categories=CATEGORIES, units=sorted(U.CONTENT_UNITS), has_vials=has_vials)


@router.post("/compounds/{cid}/edit")
def update_compound(cid: int, name: str = Form(...), category: str = Form("peptide"),
                    notes: str = Form(""), primary_unit: str = Form("mg"),
                    db: Session = Depends(get_db)):
    if not reserve_inventory_write(db):
        return services.flash_redirect("/compounds", err="Database is busy. Please retry.")
    compound = db.get(Compound, cid)
    if compound is None:
        return services.flash_redirect("/compounds", err="Compound not found.")
    name = name.strip()
    if not name or len(name) > 120:
        return services.flash_redirect(f"/compounds/{cid}/edit", err="Name must be 1–120 characters.")
    if category not in CATEGORIES or primary_unit not in U.CONTENT_UNITS:
        return services.flash_redirect(f"/compounds/{cid}/edit", err="Choose a valid category and unit.")
    if db.scalar(select(Compound.id).where(func.lower(Compound.name) == name.lower(), Compound.id != cid)):
        return services.flash_redirect(f"/compounds/{cid}/edit", err="A compound with that name already exists.")
    if name.casefold() in ("somatropin", "somatropin (hgh)", "hgh (somatropin)"):
        primary_unit = "IU"
    if primary_unit != compound.primary_unit and db.scalar(
            select(func.count()).select_from(Vial).where(Vial.compound_id == cid)):
        return services.flash_redirect(f"/compounds/{cid}/edit",
                                       err="Default unit cannot change while vials exist. Existing vial quantities must remain consistent.")
    compound.name = name
    compound.category = category
    compound.notes = notes.strip()
    compound.primary_unit = primary_unit
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        return services.flash_redirect(f"/compounds/{cid}/edit", err="That compound name is already in use.")
    return services.flash_redirect("/compounds", msg=f"Updated {name}.")
