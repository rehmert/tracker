"""Read-only unified reconstitution calculator."""

from fastapi import (
    APIRouter, Depends, HTTPException, Request
)
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Vial
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

        initial = {
            "name": vial.compound.name,
            "amount": vial.content_value,
            "unit": vial.content_unit,
            "volume_ml": vial.volume_ml,
            "vial_id": vial.id,
            "label": vial.label or f"#{vial.id}",
        }

    return render(
        request,
        "reconstitution_calculator.html",
        initial=initial,
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
