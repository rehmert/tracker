
"""Read-only record exploration tools."""

import html
import json
import sqlite3
from datetime import date
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import HTMLResponse
from sqlalchemy.engine import make_url

from .. import config

router = APIRouter(prefix="/record-explorer")

SENSITIVE = (
    "password", "secret", "token", "credential",
    "api_key", "private_key", "auth_key",
)

HIDDEN_TABLES = {"vendor_site_credentials"}


def database():
    url = make_url(config.DB_URL)
    if url.get_backend_name() != "sqlite":
        raise HTTPException(500, "SQLite required")

    path = Path(url.database)
    if not path.is_absolute():
        path = (Path(__file__).resolve().parents[1] / path).resolve()

    con = sqlite3.connect(
        path.as_uri() + "?mode=ro",
        uri=True,
    )
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA query_only=ON")
    return con


def quote(name):
    return '"' + name.replace('"', '""') + '"'


def safe(name):
    return not any(term in name.lower() for term in SENSITIVE)


def tables(db):
    return {
        row[0]
        for row in db.execute(
            "SELECT name FROM sqlite_master "
            "WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        )
        if row[0] not in HIDDEN_TABLES
    }


def columns(db, table):
    return [
        row["name"]
        for row in db.execute(
            f"PRAGMA table_info({quote(table)})"
        )
        if safe(row["name"])
    ]


def e(value):
    if value is None:
        return "—"
    return html.escape(str(value), quote=True)


def a(path, label):
    return f'<a href="{e(path)}">{e(label)}</a>'


def layout(title, body):
    navigation = " · ".join([
        a("/", "Dashboard"),
        a("/record-explorer/vials", "Vial lifecycle"),
        a("/record-explorer/notes", "Notes history"),
        a("/record-explorer/database", "Database"),
        a("/record-explorer/health", "Health"),
    ])

    return HTMLResponse(f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{e(title)} — Tracker</title>
<style>
:root {{ color-scheme:light dark; font-family:system-ui,sans-serif }}
body {{ max-width:1250px;margin:2rem auto;padding:0 1rem }}
nav {{ margin-bottom:2rem }}
a {{ color:inherit }}
table {{ width:100%;border-collapse:collapse }}
th,td {{ padding:.65rem;text-align:left;border-bottom:1px solid #8885 }}
th {{ background:#8882 }}
pre {{ white-space:pre-wrap;overflow-wrap:anywhere }}
input,select,button {{ font:inherit;padding:.4rem }}
.scroll {{ overflow-x:auto }}
.card {{ border:1px solid #8885;border-radius:12px;padding:1rem;margin:1rem 0 }}
small {{ opacity:.75 }}
</style>
</head>
<body>
<nav>{navigation}</nav>
<h1>{e(title)}</h1>
{body}
</body>
</html>""")


def table_html(rows, headings):
    head = "".join(f"<th>{e(x)}</th>" for x in headings)
    body = "".join(
        "<tr>" + "".join(f"<td>{value}</td>" for value in row)
        + "</tr>"
        for row in rows
    )
    return (
        '<div class="scroll"><table><thead><tr>'
        + head
        + '</tr></thead><tbody>'
        + body
        + '</tbody></table></div>'
    )


@router.get("/vials")
def vial_lifecycle():
    with database() as db:
        available = tables(db)

        if "vials" not in available:
            raise HTTPException(404, "Vial table unavailable")

        fields = columns(db, "vials")

        wanted = [
            "id", "label", "status", "received_on",
            "reconstituted_on", "first_punctured_on",
            "first_dosed_on", "beyond_use_on",
            "expires_on", "closed_on",
        ]

        selected = [name for name in wanted if name in fields]

        if "id" not in selected:
            raise HTTPException(500, "Vial identifier unavailable")

        projection = ",".join(quote(name) for name in selected)

        records = db.execute(
            f"SELECT {projection} FROM vials "
            "ORDER BY id DESC LIMIT 500"
        ).fetchall()

    rows = []

    for record in records:
        rows.append([
            a(f"/vials/{record['id']}", record["id"])
            if name == "id" else e(record[name])
            for name in selected
        ])

    body = (
        "<p>Lifecycle milestones recorded for each vial. "
        "Blank dates indicate missing recorded information.</p>"
        + table_html(rows, selected)
    )

    return layout("Vial lifecycle", body)


@router.get("/notes")
def notes_history():
    with database() as db:
        available = tables(db)

        if not {"pages", "page_revisions"} <= available:
            raise HTTPException(
                404, "Notes revision tables unavailable"
            )

        pages = db.execute(
            "SELECT id,title FROM pages ORDER BY title"
        ).fetchall()

        counts = dict(db.execute(
            "SELECT page_id,COUNT(*) FROM page_revisions "
            "GROUP BY page_id"
        ).fetchall())

    rows = [
        [
            a(f"/pages/{p['id']}", p["title"]),
            e(counts.get(p["id"], 0)),
            a(
                f"/record-explorer/notes/{p['id']}",
                "Compare revisions",
            ),
        ]
        for p in pages
    ]

    return layout(
        "Notes history",
        table_html(rows, ["Note", "Saved revisions", "Actions"]),
    )


@router.get("/notes/{pid}")
def notes_compare(
    pid: int,
    left: int = 0,
    right: int = 0,
):
    with database() as db:
        page = db.execute(
            "SELECT id,title,body FROM pages WHERE id=?",
            (pid,),
        ).fetchone()

        if page is None:
            raise HTTPException(404, "Note not found")

        revisions = db.execute(
            "SELECT id,title,body,created_at "
            "FROM page_revisions WHERE page_id=? "
            "ORDER BY id DESC",
            (pid,),
        ).fetchall()

    if not revisions:
        return layout(
            "Notes comparison",
            "<p>No previous revisions are available.</p>",
        )

    versions = {r["id"]: r for r in revisions}

    if not left:
        left = revisions[0]["id"]

    if right and right not in versions:
        raise HTTPException(404, "Revision not found")

    if left not in versions:
        raise HTTPException(404, "Revision not found")

    before = versions[left]["body"] or ""
    after = (
        versions[right]["body"] or ""
        if right else page["body"] or ""
    )

    import difflib

    diff = difflib.HtmlDiff(wrapcolumn=75).make_table(
        before.splitlines(),
        after.splitlines(),
        fromdesc=f"Revision {left}",
        todesc=f"Revision {right}" if right else "Current",
        context=True,
        numlines=3,
    )

    options = "".join(
        f'<option value="{r["id"]}"'
        + (" selected" if r["id"] == left else "")
        + f'>Revision {r["id"]}</option>'
        for r in revisions
    )

    right_options = (
        '<option value="0">Current</option>'
        + "".join(
            f'<option value="{r["id"]}"'
            + (" selected" if r["id"] == right else "")
            + f'>Revision {r["id"]}</option>'
            for r in revisions
        )
    )

    body = f"""
<p>{a(f"/pages/{pid}", "Open note")}</p>
<form method="get">
<label>Earlier <select name="left">{options}</select></label>
<label>Later <select name="right">{right_options}</select></label>
<button>Compare</button>
</form>
<div class="scroll">{diff}</div>
"""

    return layout(f"Notes comparison: {page['title']}", body)


@router.get("/database")
def database_explorer(
    table: str = "",
    sort: str = "",
    direction: str = "asc",
    q: str = Query("", max_length=200),
    limit: int = Query(50, ge=1, le=200),
):
    from urllib.parse import urlencode

    with database() as db:
        available = tables(db)

        if not table:
            links = [
                [a(
                    "/record-explorer/database?"
                    + urlencode({"table": name}),
                    name,
                )]
                for name in sorted(available)
            ]

            return layout(
                "Database explorer",
                "<p>Select a table to inspect.</p>"
                + table_html(links, ["Table"]),
            )

        if table not in available:
            raise HTTPException(404, "Table unavailable")

        fields = columns(db, table)

        if not fields:
            raise HTTPException(400, "No viewable columns")

        if sort and sort not in fields:
            raise HTTPException(400, "Invalid sort column")

        if direction not in ("asc", "desc"):
            raise HTTPException(400, "Invalid sort direction")

        projection = ",".join(quote(name) for name in fields)

        conditions = " OR ".join(
            f"CAST({quote(name)} AS TEXT) LIKE ?"
            for name in fields
        )

        where = f" WHERE ({conditions})" if q else ""
        params = [f"%{q}%"] * len(fields) if q else []

        order = (
            f" ORDER BY {quote(sort)} {direction.upper()}"
            if sort else ""
        )

        records = db.execute(
            f"SELECT {projection} FROM {quote(table)}"
            + where + order + " LIMIT ?",
            params + [limit],
        ).fetchall()

    headers = []

    for name in fields:
        next_direction = (
            "desc" if sort == name and direction == "asc"
            else "asc"
        )

        query = urlencode({
            "table": table,
            "sort": name,
            "direction": next_direction,
            "q": q,
            "limit": limit,
        })

        headers.append(
            a("/record-explorer/database?" + query, name)
        )

    rows = [
        [e(record[name]) for name in fields]
        for record in records
    ]

    body = f"""
<p>{a("/record-explorer/database", "All tables")}</p>
<form method="get">
<input type="hidden" name="table" value="{e(table)}">
<label>Search
<input name="q" value="{e(q)}">
</label>
<label>Rows
<input type="number" name="limit"
min="1" max="200" value="{limit}">
</label>
<button>Apply</button>
</form>
<p><small>Read-only. Sensitive columns and credential
tables are excluded. Search is limited to visible columns.</small></p>
"""

    return layout(
        f"Database: {table}",
        body + table_html(rows, headers),
    )


@router.get("/health")
def health_explorer():
    with database() as db:
        available = tables(db)

        if "vital_readings" not in available:
            raise HTTPException(
                404, "Vital readings unavailable"
            )

        fields = columns(db, "vital_readings")

        wanted = [
            "measured_at", "weight_kg", "systolic",
            "diastolic", "pulse_bpm",
        ]

        selected = [name for name in wanted if name in fields]

        if not selected:
            raise HTTPException(
                404, "Vital measurement columns unavailable"
            )

        projection = ",".join(quote(x) for x in selected)

        order = (
            "measured_at" if "measured_at" in selected
            else selected[0]
        )

        records = db.execute(
            f"SELECT {projection} FROM vital_readings "
            f"ORDER BY {quote(order)} DESC LIMIT 200"
        ).fetchall()

    rows = [
        [e(record[name]) for name in selected]
        for record in records
    ]

    body = """
<p>Recorded vital measurements, newest first.</p>
<p>
""" + " · ".join([
        a("/health-insights", "Health insights"),
        a("/health-timeline", "Health timeline"),
        a("/labs", "Laboratory results"),
        a("/labs/compare", "Compare laboratory reports"),
    ]) + "</p>"

    body += table_html(rows, selected)

    return layout("Health record explorer", body)
