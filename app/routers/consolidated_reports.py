
"""Read-only consolidated reporting workspace."""

import csv
import io
from datetime import date, datetime, time

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import (
    Compound,
    Vial,
    DoseLog,
    Protocol,
    VitalReading,
    LabReport,
    LabResult,
    Purchase,
)
from ..templating import render

router = APIRouter()


DATASETS = {
    "administrations": DoseLog,
    "vitals": VitalReading,
    "laboratory_results": LabResult,
    "inventory": Vial,
    "protocols": Protocol,
    "purchases": Purchase,
}


def _date_column(name, model):
    candidates = {
        "administrations": ("taken_at",),
        "vitals": ("measured_at",),
        "laboratory_results": (),
        "inventory": ("created_at",),
        "protocols": ("created_at",),
        "purchases": ("purchased_on",),
    }

    for column in candidates.get(name, ()):
        if hasattr(model, column):
            return getattr(model, column)

    return None


def _filtered_query(name, model, start, end):
    query = select(model)
    column = _date_column(name, model)

    if column is None:
        return query

    if start is not None:
        query = query.where(
            column >= datetime.combine(start, time.min)
            if isinstance(column.type, type(None))
            else start
        )

    if end is not None:
        query = query.where(column <= end)

    return query


def _query(name, model, start, end):
    """Apply date filtering using model column types."""
    from sqlalchemy import DateTime

    query = select(model)
    column = _date_column(name, model)

    if column is None:
        return query

    if isinstance(column.type, DateTime):
        if start:
            query = query.where(
                column >= datetime.combine(start, time.min)
            )

        if end:
            query = query.where(
                column <= datetime.combine(end, time.max)
            )
    else:
        if start:
            query = query.where(column >= start)

        if end:
            query = query.where(column <= end)

    return query


def _validate(start_date, end_date):
    if (
        start_date is not None
        and end_date is not None
        and start_date > end_date
    ):
        raise HTTPException(
            400,
            "Start date cannot be after end date",
        )


def _lab_result_query(start, end):
    query = (
        select(LabResult)
        .join(
            LabReport,
            LabResult.report_id == LabReport.id,
        )
    )

    if start:
        query = query.where(LabReport.drawn_on >= start)

    if end:
        query = query.where(LabReport.drawn_on <= end)

    return query


def _dataset_query(name, start, end):
    if name == "laboratory_results":
        return _lab_result_query(start, end)

    return _query(
        name,
        DATASETS[name],
        start,
        end,
    )


@router.get("/reports")
def reports(
    request: Request,
    start_date: date | None = None,
    end_date: date | None = None,
    db: Session = Depends(get_db),
):
    _validate(start_date, end_date)

    counts = {}

    for name, model in DATASETS.items():
        query = _dataset_query(
            name,
            start_date,
            end_date,
        )

        counts[name] = db.scalar(
            select(func.count()).select_from(
                query.subquery()
            )
        ) or 0

    return render(
        request,
        "consolidated_reports.html",
        counts=counts,
        start_date=start_date,
        end_date=end_date,
        datasets=DATASETS,
    )


@router.get("/reports/{dataset}.csv")
def export_report(
    dataset: str,
    start_date: date | None = None,
    end_date: date | None = None,
    db: Session = Depends(get_db),
):
    _validate(start_date, end_date)

    model = DATASETS.get(dataset)

    if model is None:
        raise HTTPException(404, "Unknown dataset")

    columns = [
        column.name
        for column in model.__table__.columns
    ]

    query = _dataset_query(
        dataset,
        start_date,
        end_date,
    )

    def rows():
        buffer = io.StringIO()
        writer = csv.writer(buffer)

        writer.writerow(columns)
        yield buffer.getvalue()
        buffer.seek(0)
        buffer.truncate(0)

        for record in db.scalars(
            query.execution_options(yield_per=500)
        ):
            writer.writerow([
                getattr(record, column)
                for column in columns
            ])

            yield buffer.getvalue()
            buffer.seek(0)
            buffer.truncate(0)

    filename = f"tracker_{dataset}.csv"

    return StreamingResponse(
        rows(),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition":
                f'attachment; filename="{filename}"'
        },
    )
