from fastapi import APIRouter, Depends, Form, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import services, units as U
from ..db import get_db
from ..models import CATEGORIES, Compound, ProtocolItem, Vial, page_compounds
from ..templating import render

router = APIRouter()


@router.get("/compounds")
def compounds_page(request: Request, db: Session = Depends(get_db)):
    compounds = list(db.scalars(select(Compound).order_by(Compound.name)))
    notes = dict(db.execute(select(page_compounds.c.compound_id, func.count())
                            .group_by(page_compounds.c.compound_id)).all())
    return render(request, "compounds.html", compounds=compounds, notes=notes,
                  refs=services.compound_refs(db), categories=CATEGORIES)


@router.post("/compounds")
def create_compound(name: str = Form(...), category: str = Form("peptide"),
                    notes: str = Form(""), primary_unit: str = Form("mg"), db: Session = Depends(get_db)):
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
