
"""Read-only inventory activity timeline."""

from datetime import date, datetime, time

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import (
    Compound,
    Vial,
    DoseLog,
    PreparationEvent,
    ChangeAudit,
)
from .. import services
from ..templating import render

router = APIRouter()


def _timestamp(value):
    """Normalize dates for chronological display."""
    if isinstance(value, datetime):
        return value.replace(tzinfo=None)
    if isinstance(value, date):
        return datetime.combine(value, time.min)
    return datetime.min


def _event(when, category, description, detail="", source=""):
    return {
        "when": when,
        "category": category,
        "description": description,
        "detail": detail,
        "source": source,
    }


@router.get("/inventory-timeline")
def inventory_timeline(
    request: Request,
    compound_id: int | None = None,
    vial_id: int | None = None,
    db: Session = Depends(get_db),
):
    compounds = list(
        db.scalars(
            select(Compound).order_by(Compound.name)
        )
    )

    vials = list(
        db.scalars(
            select(Vial).order_by(Vial.id.desc())
        )
    )

    if compound_id is not None:
        vials = [
            vial for vial in vials
            if vial.compound_id == compound_id
        ]

    selected = None
    events = []
    view = None

    if vial_id is not None:
        selected = db.get(Vial, vial_id)

        if selected is None:
            raise HTTPException(404, "Vial not found")

        if (
            compound_id is not None
            and selected.compound_id != compound_id
        ):
            raise HTTPException(
                400,
                "Vial does not belong to selected compound",
            )

        view = services.vial_views(db, [selected])[selected.id]

        # Initial inventory record.
        events.append(
            _event(
                selected.created_at,
                "Inventory",
                "Vial added to Tracker",
                (
                    f"Initial content: "
                    f"{selected.content_value:g} "
                    f"{selected.content_unit}"
                ),
                f"Vial #{selected.id}",
            )
        )

        # Purchase.
        if selected.purchase is not None:
            purchase = selected.purchase

            events.append(
                _event(
                    purchase.purchased_on,
                    "Purchase",
                    "Purchased",
                    purchase.vendor,
                    f"Purchase #{purchase.id}",
                )
            )

        # Lifecycle dates.
        lifecycle = [
            (
                selected.received_on,
                "Received",
                "Vial received",
            ),
            (
                selected.reconstituted_on,
                "Reconstitution",
                "Reconstitution date recorded",
            ),
            (
                selected.first_punctured_on,
                "Preparation",
                "First puncture recorded",
            ),
            (
                selected.first_dosed_on,
                "Administration",
                "First dose date recorded",
            ),
            (
                selected.closed_on,
                "Closure",
                "Vial closed",
            ),
        ]

        for when, category, description in lifecycle:
            if when is not None:
                events.append(
                    _event(
                        when,
                        category,
                        description,
                        source="Vial record",
                    )
                )

        # Recorded administrations and waste.
        doses = list(
            db.scalars(
                select(DoseLog)
                .where(DoseLog.vial_id == selected.id)
                .order_by(
                    DoseLog.taken_at.desc(),
                    DoseLog.id.desc(),
                )
            )
        )

        for dose in doses:
            category = (
                "Waste"
                if dose.kind == "waste"
                else "Administration"
            )

            events.append(
                _event(
                    dose.taken_at,
                    category,
                    (
                        "Quantity discarded"
                        if dose.kind == "waste"
                        else "Dose recorded"
                    ),
                    (
                        f"{dose.entered_value:g} "
                        f"{dose.entered_unit}"
                        + (
                            f" · {dose.site}"
                            if dose.site else ""
                        )
                    ),
                    f"Dose #{dose.id}",
                )
            )

        # Preparation events.
        preparations = list(
            db.scalars(
                select(PreparationEvent)
                .where(
                    PreparationEvent.vial_id == selected.id
                )
                .order_by(
                    PreparationEvent.occurred_at.desc()
                )
            )
        )

        for preparation in preparations:
            events.append(
                _event(
                    preparation.occurred_at,
                    "Preparation",
                    preparation.kind.replace(
                        "_", " "
                    ).title(),
                    preparation.notes or "",
                    f"Preparation #{preparation.id}",
                )
            )

        # Existing change audit records.
        audits = list(
            db.scalars(
                select(ChangeAudit)
                .where(
                    ChangeAudit.entity_type == "vial",
                    ChangeAudit.entity_id == selected.id,
                )
                .order_by(ChangeAudit.created_at.desc())
            )
        )

        for audit in audits:
            events.append(
                _event(
                    audit.created_at,
                    "Audit",
                    audit.action.replace("_", " ").title(),
                    "Recorded inventory change",
                    f"Audit #{audit.id}",
                )
            )

        events.sort(
            key=lambda event: _timestamp(event["when"]),
            reverse=True,
        )

    return render(
        request,
        "inventory_timeline.html",
        compounds=compounds,
        vials=vials,
        compound_id=compound_id,
        vial_id=vial_id,
        selected=selected,
        view=view,
        events=events,
    )
