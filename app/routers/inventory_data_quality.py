"""TRACKER_RELEASE_233_240

Read-only vial-level FEFO data-quality review.
"""

from datetime import date
from math import isfinite

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Vial
from ..services import vial_views
from ..templating import render

router = APIRouter()


def classify_vials(vials, views, today=None):
    """Classify active, nonempty vials excluded by FEFO dates.

    The same eligibility, effective-date and unit
    conventions are used by build_fefo().

    This function does not change database records.
    """
    today = today or date.today()
    results = []

    for vial in vials:
        if vial.status not in ("sealed", "in_use"):
            continue

        if vial.closed_on is not None:
            continue

        view = views.get(vial.id)
        if view is None:
            continue

        try:
            remaining_base = float(view.remaining_base)
        except (ValueError, TypeError, OverflowError):
            continue

        if (
            not isfinite(remaining_base)
            or remaining_base <= 0
        ):
            continue

        unit = "IU" if view.dim == "iu" else "mg"
        scale = 1 if unit == "IU" else 1000

        dates = [
            value
            for value in (
                vial.expires_on,
                vial.beyond_use_on,
            )
            if value is not None
        ]

        effective_expiry = min(dates) if dates else None

        if effective_expiry is None:
            issue = "undated"
            issue_label = "Missing expiration dates"
        elif effective_expiry < today:
            issue = "expired"
            issue_label = "Already expired"
        else:
            continue

        results.append({
            "id": vial.id,
            "compound_id": vial.compound_id,
            "compound": vial.compound.name,
            "label": vial.label or f"Vial #{vial.id}",
            "lot": vial.lot or "",
            "status": vial.status,
            "unit": unit,
            "remaining": remaining_base / scale,
            "expires_on": vial.expires_on,
            "beyond_use_on": vial.beyond_use_on,
            "effective_expiry": effective_expiry,
            "issue": issue,
            "issue_label": issue_label,
        })

    results.sort(
        key=lambda row: (
            0 if row["issue"] == "expired" else 1,
            row["effective_expiry"] or date.max,
            row["compound"].casefold(),
            row["id"],
        )
    )

    return results


def filter_issues(rows, compound="", issue="all"):
    needle = compound.strip().casefold()

    if issue not in ("all", "undated", "expired"):
        issue = "all"

    return [
        row
        for row in rows
        if (
            not needle
            or needle in row["compound"].casefold()
        )
        and (
            issue == "all"
            or row["issue"] == issue
        )
    ]


def issue_summary(rows):
    return {
        "total": len(rows),
        "undated": sum(
            row["issue"] == "undated"
            for row in rows
        ),
        "expired": sum(
            row["issue"] == "expired"
            for row in rows
        ),
    }


@router.get("/inventory-data-quality")
def inventory_data_quality(
    request: Request,
    compound: str = Query("", max_length=120),
    issue: str = Query("all"),
    db: Session = Depends(get_db),
):
    if issue not in ("all", "undated", "expired"):
        issue = "all"

    vials = list(
        db.scalars(
            select(Vial).order_by(Vial.id)
        ).all()
    )

    views = vial_views(db, vials)

    all_rows = classify_vials(
        vials,
        views,
    )

    rows = filter_issues(
        all_rows,
        compound,
        issue,
    )

    return render(
        request,
        "inventory_data_quality.html",
        rows=rows,
        totals=issue_summary(all_rows),
        compound=compound,
        issue=issue,
    )
