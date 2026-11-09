"""Release 468: private, read-only SQLAlchemy integration.

Uses the already verified secondary session and staged
workspace. Never modifies the administrator's global
engine or exposes a user-selected database.
"""
from contextlib import contextmanager
from html import escape
from urllib.parse import quote

from fastapi import HTTPException
from sqlalchemy import create_engine, event, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.pool import NullPool

from .secondary_request_db467 import (
    verified_private_scope467,
)


@contextmanager
def private_orm468(request):
    scope = verified_private_scope467(request)

    uri = (
        "sqlite:///file:"
        + quote(str(scope.database), safe="/")
        + "?mode=ro&uri=true"
    )

    engine = create_engine(
        uri,
        poolclass=NullPool,
        connect_args={"timeout": 5},
    )

    @event.listens_for(engine, "connect")
    def _readonly468(connection, _record):
        cursor = connection.cursor()
        try:
            cursor.execute("PRAGMA query_only=ON")
            value = cursor.execute(
                "PRAGMA query_only"
            ).fetchone()

            if value != (1,):
                raise RuntimeError(
                    "Read-only protection unavailable"
                )
        finally:
            cursor.close()

    try:
        with engine.connect() as db:
            marker = db.execute(text("""
                SELECT user_id,status,schema_version
                FROM tracker_staged_workspace426
            """)).all()

            if [tuple(row) for row in marker] != [
                (scope.user_id, "inactive", 426)
            ]:
                raise RuntimeError(
                    "Private ORM workspace mismatch"
                )

            yield scope, db
    except (SQLAlchemyError, RuntimeError, OSError):
        raise HTTPException(
            503, "Private ORM database unavailable"
        ) from None
    finally:
        engine.dispose()


COUNTS468 = {
    "compounds": "compounds",
    "vials": "vials",
    "doses": "dose_logs",
    "vitals": "vital_readings",
    "food": "tracker_food_entries",
    "water": "tracker_water_entries",
}


def private_summary468(request):
    with private_orm468(request) as (scope, db):
        counts = {}

        # All SQL identifiers come from this fixed allowlist.
        for key, table in COUNTS468.items():
            value = db.execute(
                text(f"SELECT COUNT(*) FROM {table}")
            ).scalar_one()

            if type(value) is not int or value < 0:
                raise HTTPException(
                    503, "Invalid private record count"
                )
            counts[key] = value

        vitals = [
            {
                "at": row[0],
                "weight_kg": row[1],
                "systolic": row[2],
                "diastolic": row[3],
                "pulse_bpm": row[4],
            }
            for row in db.execute(text("""
                SELECT measured_at,weight_kg,systolic,
                       diastolic,pulse_bpm
                FROM vital_readings
                ORDER BY measured_at DESC,id DESC
                LIMIT 5
            """))
        ]

        doses = [
            {
                "at": row[0],
                "compound": row[1],
                "amount": row[2],
                "unit": row[3],
            }
            for row in db.execute(text("""
                SELECT d.taken_at,c.name,
                       d.entered_value,d.entered_unit
                FROM dose_logs AS d
                JOIN vials AS v ON v.id=d.vial_id
                JOIN compounds AS c ON c.id=v.compound_id
                ORDER BY d.taken_at DESC,d.id DESC
                LIMIT 5
            """))
        ]

        foods = [
            {
                "day": row[0],
                "name": row[1],
                "servings": row[2],
            }
            for row in db.execute(text("""
                SELECT e.eaten_on,p.name,e.servings
                FROM tracker_food_entries AS e
                JOIN tracker_food_products AS p
                  ON p.id=e.product_id
                ORDER BY e.eaten_on DESC,e.id DESC
                LIMIT 5
            """))
        ]

    report = {
        "mode": "private-orm-summary468",
        "user_id": scope.user_id,
        "storage_mode": scope.mode,
        "read_only": True,
        "normal_login_enabled": False,
        "counts": counts,
        "recent": {
            "vitals": vitals,
            "doses": doses,
            "food": foods,
        },
    }

    return report


def render_summary468(report):
    if (
        type(report) is not dict
        or report.get("mode") != "private-orm-summary468"
        or type(report.get("user_id")) is not int
        or report["user_id"] <= 1
        or report.get("read_only") is not True
        or report.get("normal_login_enabled") is not False
        or type(report.get("counts")) is not dict
        or set(report["counts"]) != set(COUNTS468)
        or type(report.get("recent")) is not dict
        or set(report["recent"]) != {
            "vitals", "doses", "food"
        }
    ):
        raise ValueError("Invalid private ORM summary")

    def recent_card(title, entries, keys):
        rows = []

        for item in entries:
            if type(item) is not dict:
                raise ValueError("Invalid recent item")

            values = [
                escape(
                    "—" if item.get(key) is None
                    else str(item.get(key)),
                    quote=True,
                )
                for key in keys
            ]
            rows.append(
                "<li>" + " · ".join(values) + "</li>"
            )

        if not rows:
            rows = ["<li>No records yet.</li>"]

        return (
            "<section><h2>" + escape(title)
            + "</h2><ul>"
            + "".join(rows)
            + "</ul></section>"
        )

    counts = "".join(
        "<div class='stat'><span>"
        + escape(label.replace("_", " ").title())
        + "</span><strong>"
        + str(report["counts"][label])
        + "</strong></div>"
        for label in COUNTS468
    )

    recent = (
        recent_card(
            "Recent Vitals",
            report["recent"]["vitals"],
            ("at", "weight_kg", "systolic",
             "diastolic", "pulse_bpm"),
        )
        + recent_card(
            "Recent Doses",
            report["recent"]["doses"],
            ("at", "compound", "amount", "unit"),
        )
        + recent_card(
            "Recent Food",
            report["recent"]["food"],
            ("day", "name", "servings"),
        )
    )

    return f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport"
content="width=device-width,initial-scale=1">
<meta name="referrer" content="no-referrer">
<title>Private Data Summary · Tracker</title>
<style>
*{{box-sizing:border-box}}
body{{margin:0;background:#f3f6fa;color:#182333;
font:16px/1.45 system-ui,sans-serif}}
main{{max-width:940px;margin:auto;padding:16px}}
nav{{display:flex;gap:10px;flex-wrap:wrap}}
nav a{{display:inline-flex;align-items:center;
min-height:44px;padding:10px;border-radius:8px;
background:#e2eef9;color:#174f80}}
.grid{{display:grid;grid-template-columns:
repeat(2,minmax(0,1fr));gap:10px}}
.stat,section{{background:white;
border:1px solid #ced9e5;border-radius:12px;
padding:14px;margin:10px 0}}
.stat span{{display:block;font-size:.85rem}}
.stat strong{{font-size:1.6rem}}
li{{margin:8px 0;overflow-wrap:anywhere}}
.note{{color:#405166;font-size:.9rem}}
@media(min-width:720px){{
.grid{{grid-template-columns:
repeat(3,minmax(0,1fr))}}
}}
</style></head>
<body><main>
<nav>
<a href="/secondary/overview">Workspace</a>
<a href="/secondary/food">Food</a>
<a href="/secondary/vitals">Vitals</a>
<a href="/secondary/doses">Doses</a>
<a href="/secondary/data-context">DB Context</a>
</nav>
<h1>Private Data Summary</h1>
<p>Account {report["user_id"]} ·
Authenticated read-only SQLAlchemy context</p>
<div class="grid">{counts}</div>
{recent}
<p class="note">Only this account's records are shown.
Normal multi-user application login remains disabled.</p>
</main></body></html>'''
