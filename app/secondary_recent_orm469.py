"""Release 469: migrate real pilot vitals/doses pages to
authenticated, read-only, per-user SQLAlchemy connections.

No account IDs, database names, paths or SQL are accepted
from the browser. Existing write workers remain unchanged.
"""
from fastapi import HTTPException
from sqlalchemy import text

from .secondary_orm468 import private_orm468


ACTIONS469 = frozenset(("vitals", "doses"))

QUERIES469 = {
    "vitals": text("""
        SELECT measured_at AS at,
               weight_kg,
               systolic,
               diastolic,
               pulse_bpm,
               substr(context,1,80) AS context
        FROM vital_readings
        ORDER BY measured_at DESC,id DESC
        LIMIT 10
    """),
    "doses": text("""
        SELECT d.taken_at AS at,
               substr(c.name,1,120) AS compound,
               d.entered_value AS amount,
               d.entered_unit AS unit,
               d.kind AS kind,
               substr(d.site,1,80) AS site
        FROM dose_logs AS d
        JOIN vials AS v
          ON v.id=d.vial_id
        JOIN compounds AS c
          ON c.id=v.compound_id
        ORDER BY d.taken_at DESC,d.id DESC
        LIMIT 10
    """),
}

FIELDS469 = {
    "vitals": frozenset((
        "at", "weight_kg", "systolic",
        "diastolic", "pulse_bpm", "context",
    )),
    "doses": frozenset((
        "at", "compound", "amount",
        "unit", "kind", "site",
    )),
}


def read_recent_orm469(request, kind):
    if type(kind) is not str or kind not in ACTIONS469:
        raise ValueError("Unsupported private record type")

    with private_orm468(request) as (scope, db):
        rows = db.execute(
            QUERIES469[kind]
        ).mappings().all()

        items = [dict(row) for row in rows]

    if (
        scope.user_id <= 1
        or len(items) > 10
        or any(
            type(item) is not dict
            or set(item) != FIELDS469[kind]
            for item in items
        )
    ):
        raise HTTPException(
            503, "Private recent-record contract invalid"
        )

    return {
        "mode": "private-recent-orm469",
        "user_id": scope.user_id,
        "kind": kind,
        "items": items,
        "read_only": True,
    }
