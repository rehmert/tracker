"""Release 652: COA test-type catalog management.

Editing a name or category never rewrites historical attachment values.
Disabling a type hides it from new uploads but preserves old selections.
"""
from fastapi import APIRouter, Depends, Form, Request
from sqlalchemy.orm import Session

from .. import services
from ..coa_catalog652 import catalog652
from ..models import CoaTestType652
from ..scoped_db390 import get_scoped_db390
from ..templating import render

router = APIRouter()


def _clean(label, group, rows, exclude_id=None):
    label = (label or "").strip()
    group = (group or "").strip()
    if not 1 <= len(label) <= 100 or not 1 <= len(group) <= 60:
        raise ValueError("Type name (1–100 characters) and group (1–60 characters) are required.")
    if any(ord(c) < 32 for c in label + group):
        raise ValueError("Control characters are not allowed.")
    if any(row.id != exclude_id and row.label.casefold() == label.casefold() for row in rows):
        raise ValueError("A COA test type already uses that name.")
    if label.startswith(("~651~", "~652~", "@652:")):
        raise ValueError("That name uses reserved catalog syntax.")
    return label, group


@router.get("/coa-test-types")
def manage_coa_test_types(request: Request, db: Session = Depends(get_scoped_db390)):
    rows = catalog652(db)
    return render(request, "coa_test_types_manage652.html", types=rows)


@router.post("/coa-test-types")
def create_coa_test_type(label: str = Form(""), group_name: str = Form(""),
                         db: Session = Depends(get_scoped_db390)):
    try:
        label, group = _clean(label, group_name, catalog652(db))
    except ValueError as exc:
        return services.flash_redirect("/coa-test-types", err=str(exc))
    db.add(CoaTestType652(label=label, group_name=group, active=True, position=100))
    db.commit()
    return services.flash_redirect("/coa-test-types", msg="COA test type added.")


@router.post("/coa-test-types/{type_id}/edit")
def update_coa_test_type(type_id: int, label: str = Form(""),
                         group_name: str = Form(""),
                         db: Session = Depends(get_scoped_db390)):
    row = db.get(CoaTestType652, type_id)
    if row is None:
        return services.flash_redirect("/coa-test-types", err="COA test type no longer exists.")
    try:
        label, group = _clean(label, group_name, catalog652(db), type_id)
    except ValueError as exc:
        return services.flash_redirect("/coa-test-types", err=str(exc))
    row.label, row.group_name = label, group
    db.commit()
    return services.flash_redirect("/coa-test-types", msg="COA test type updated.")


@router.post("/coa-test-types/{type_id}/toggle")
def toggle_coa_test_type(type_id: int, db: Session = Depends(get_scoped_db390)):
    row = db.get(CoaTestType652, type_id)
    if row is None:
        return services.flash_redirect("/coa-test-types", err="COA test type no longer exists.")
    row.active = not row.active
    db.commit()
    return services.flash_redirect(
        "/coa-test-types",
        msg="COA test type activated." if row.active else "COA test type deactivated.",
    )
