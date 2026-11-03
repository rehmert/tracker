"""Read-only unified reconstitution calculator."""

from fastapi import (
    APIRouter, Depends, HTTPException, Request
)
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ..db import get_db
from ..models import Vial
from .. import services, units as U
from ..reconstitution_math import calculate
from ..templating import render

router = APIRouter()


@router.get("/reconstitution-calculator")
def calculator_page(
    request: Request,
    vial_id: int | None = None,
    db: Session = Depends(get_db),
):
    initial = None

    if vial_id is not None:
        vial = db.get(Vial, vial_id)

        if vial is None:
            raise HTTPException(404, "Vial not found")

        view = services.vial_views(db, [vial])[vial.id]

        original_amount = U.from_base(
            view.content_base, vial.content_unit
        )
        remaining_amount = U.from_base(
            view.remaining_base, vial.content_unit
        )

        label_base, label_dimension = U.to_base(
            vial.content_value, vial.content_unit
        )

        coa_applied = False
        if vial.use_coa_content:
            for coa in vial.all_coas:
                if (
                    coa.reported_content_value is None
                    or not coa.reported_content_unit
                ):
                    continue

                try:
                    coa_base, coa_dimension = U.to_base(
                        coa.reported_content_value,
                        coa.reported_content_unit,
                    )
                except (U.UnitError, ValueError, TypeError):
                    continue

                if (
                    coa_dimension == label_dimension
                    and 0 < coa_base < float("inf")
                ):
                    coa_applied = True
                    break

        initial = {
            "name": vial.compound.name,
            "amount": original_amount,
            "unit": vial.content_unit,
            "volume_ml": vial.volume_ml,
            "vial_id": vial.id,
            "label": vial.label or f"#{vial.id}",
            "label_amount": vial.content_value,
            "content_source": (
                "COA average" if coa_applied else "label"
            ),
            "remaining_amount": remaining_amount,
            "partial": (
                view.remaining_base < view.content_base
                - max(1e-6, view.content_base * 1e-7)
            ),
            "status": vial.status,
        }

    recent = list(db.scalars(
        select(Vial)
        .options(selectinload(Vial.compound))
        .where(Vial.status.in_(("sealed", "in_use")))
        .order_by(Vial.id.desc())
        .limit(250)
    ))

    recent.sort(
        key=lambda v: (v.compound.name.casefold(), -v.id)
    )

    return render(
        request,
        "reconstitution_calculator.html",
        initial=initial,
        recent_vials=recent,
    )


@router.post("/reconstitution-calculator/preview")
async def calculator_preview(request: Request):
    try:
        data = await request.json()
        result = calculate(data)

        return JSONResponse(
            result,
            headers={"Cache-Control": "no-store"},
        )

    except (
        ValueError,
        TypeError,
        OverflowError,
        ZeroDivisionError,
    ) as exc:
        return JSONResponse(
            {"error": str(exc)},
            status_code=422,
            headers={"Cache-Control": "no-store"},
        )
