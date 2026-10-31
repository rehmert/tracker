"""TRACKER_RELEASE_233_240

Read-only vial-level FEFO data-quality review.
"""

from datetime import date
from math import isfinite
import csv
import io

from fastapi.responses import Response

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

        # TRACKER_RELEASE_241_248
        days_overdue = (
            (today - effective_expiry).days
            if effective_expiry is not None
            else None
        )

        if issue == "undated":
            review_priority = "Date review"
        elif days_overdue >= 90:
            review_priority = "Expired 90+ days"
        elif days_overdue >= 30:
            review_priority = "Expired 30+ days"
        else:
            review_priority = "Recently expired"

        results.append({
            "days_overdue": days_overdue,
            "review_priority": review_priority,
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


def filter_issues(
    rows,
    compound="",
    issue="all",
    overdue="all",
    sort="oldest",
):
    """Filter and sort vial-level review records.

    Overdue filters apply only to already-expired vials.
    Undated vials remain visible when issue='all'.
    """
    needle = (compound or "").strip().casefold()

    if issue not in ("all", "undated", "expired"):
        issue = "all"

    if overdue not in ("all", "30", "90"):
        overdue = "all"

    if sort not in (
        "oldest",
        "newest",
        "compound",
        "remaining",
    ):
        sort = "oldest"

    selected = []

    for row in rows:
        if needle and needle not in row["compound"].casefold():
            continue

        if issue != "all" and row["issue"] != issue:
            continue

        if overdue != "all" and row["issue"] == "expired":
            if (row.get("days_overdue") or 0) < int(overdue):
                continue

        selected.append(row)

    if sort == "oldest":
        selected.sort(
            key=lambda r: (
                0 if r["issue"] == "expired" else 1,
                -(r.get("days_overdue") or 0),
                r["compound"].casefold(),
                r["id"],
            )
        )

    elif sort == "newest":
        selected.sort(
            key=lambda r: (
                0 if r["issue"] == "expired" else 1,
                r.get("days_overdue") or 0,
                r["compound"].casefold(),
                r["id"],
            )
        )

    elif sort == "compound":
        selected.sort(
            key=lambda r: (
                r["compound"].casefold(),
                r["id"],
            )
        )

    elif sort == "remaining":
        # Quantities are not comparable across units.
        # Group by unit before sorting by quantity.
        selected.sort(
            key=lambda r: (
                r["unit"],
                -r["remaining"],
                r["compound"].casefold(),
                r["id"],
            )
        )

    return selected


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
    overdue: str = Query("all"),
    sort: str = Query("oldest"),
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
        compound=compound,
        issue=issue,
        overdue=overdue,
        sort=sort,
    )

    return render(
        request,
        "inventory_data_quality.html",
        rows=rows,
        totals=issue_summary(all_rows),
        filtered_count=len(rows),
        compound=compound,
        issue=issue,
        overdue=overdue,
        sort=sort,
    )


# TRACKER_RELEASE_241_248_CSV

def safe_csv_text(value):
    """Prevent spreadsheet formula interpretation."""
    text = str(value if value is not None else "")

    if text.lstrip().startswith(("=", "+", "-", "@")):
        return "'" + text

    return text


@router.get("/inventory-data-quality.csv")
def inventory_data_quality_csv(
    compound: str = Query("", max_length=120),
    issue: str = Query("all"),
    overdue: str = Query("all"),
    sort: str = Query("oldest"),
    db: Session = Depends(get_db),
):
    vials = list(
        db.scalars(
            select(Vial).order_by(Vial.id)
        ).all()
    )

    views = vial_views(db, vials)

    rows = filter_issues(
        classify_vials(vials, views),
        compound=compound,
        issue=issue,
        overdue=overdue,
        sort=sort,
    )

    output = io.StringIO()
    writer = csv.writer(output)

    writer.writerow([
        "Vial ID",
        "Compound",
        "Label",
        "Lot",
        "Status",
        "Issue",
        "Review priority",
        "Days overdue",
        "Remaining quantity",
        "Unit",
        "Expiration date",
        "Beyond-use date",
        "Effective expiration",
        "Vial detail path",
    ])

    for row in rows:
        writer.writerow([
            row["id"],
            safe_csv_text(row["compound"]),
            safe_csv_text(row["label"]),
            safe_csv_text(row["lot"]),
            row["status"],
            row["issue_label"],
            row["review_priority"],
            (
                row["days_overdue"]
                if row["days_overdue"] is not None
                else ""
            ),
            round(row["remaining"], 4),
            row["unit"],
            row["expires_on"] or "",
            row["beyond_use_on"] or "",
            row["effective_expiry"] or "",
            f'/vials/{row["id"]}',
        ])

    return Response(
        "\ufeff" + output.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition":
            'attachment; filename="inventory-data-quality.csv"'
        },
    )
