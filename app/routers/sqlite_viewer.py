
"""Read-only SQLite database browser for Tracker."""

import sqlite3
from pathlib import Path
from urllib.parse import urlencode

from fastapi import APIRouter, HTTPException, Request
from sqlalchemy.engine import make_url

from .. import config
from ..templating import render

router = APIRouter()

PAGE_SIZES = (25, 50, 100)
MAX_SEARCH_LENGTH = 200


def _database_path():
    url = make_url(config.DB_URL)

    if url.get_backend_name() != "sqlite":
        raise HTTPException(
            503,
            "SQLite viewer requires a SQLite database.",
        )

    database = url.database

    if not database or database == ":memory:":
        raise HTTPException(
            503,
            "SQLite viewer requires a file-backed database.",
        )

    path = Path(database)

    if not path.is_absolute():
        path = Path(config.BASE_DIR).parent / path

    path = path.resolve()

    if not path.is_file():
        raise HTTPException(
            503,
            "Configured database file was not found.",
        )

    return path


def _connection():
    path = _database_path()

    # SQLite URI mode=ro prevents writes.
    uri = path.as_uri() + "?mode=ro"

    connection = sqlite3.connect(
        uri,
        uri=True,
        timeout=5,
    )

    # Defense in depth: reject write statements.
    connection.execute("PRAGMA query_only=ON")
    connection.row_factory = sqlite3.Row

    return connection


def _quote_identifier(value):
    return '"' + value.replace('"', '""') + '"'


def _tables(connection):
    rows = connection.execute(
        """
        SELECT name
        FROM sqlite_master
        WHERE type = 'table'
          AND name NOT LIKE 'sqlite_%'
        ORDER BY name COLLATE NOCASE
        """
    ).fetchall()

    return [row["name"] for row in rows]


def _columns(connection, table):
    # Table name must already have passed allowlist validation.
    quoted = _quote_identifier(table)

    return connection.execute(
        f"PRAGMA table_info({quoted})"
    ).fetchall()


def _display_value(value):
    if value is None:
        return "NULL"

    if isinstance(value, bytes):
        return f"<binary: {len(value)} bytes>"

    text = str(value)

    if len(text) > 500:
        return text[:500] + "…"

    return text


@router.get("/sqlite-viewer")
def sqlite_viewer(
    request: Request,
    table: str = "",
    page: int = 1,
    page_size: int = 25,
    q: str = "",
):
    if page < 1:
        raise HTTPException(
            400,
            "Page must be at least 1.",
        )

    if page_size not in PAGE_SIZES:
        raise HTTPException(
            400,
            "Unsupported page size.",
        )

    q = q.strip()

    if len(q) > MAX_SEARCH_LENGTH:
        raise HTTPException(
            400,
            "Search text is too long.",
        )

    connection = _connection()

    try:
        tables = _tables(connection)

        if not table and tables:
            table = tables[0]

        if table and table not in tables:
            raise HTTPException(
                404,
                "Unknown database table.",
            )

        columns = (
            _columns(connection, table)
            if table else []
        )

        names = [
            column["name"]
            for column in columns
        ]

        records = []
        total = 0
        total_pages = 1

        if table:
            quoted_table = _quote_identifier(table)

            where = ""
            parameters = []

            if q and names:
                # Search only known columns from PRAGMA table_info.
                # Bound parameters prevent SQL injection.
                conditions = []

                for name in names:
                    quoted_name = _quote_identifier(name)

                    conditions.append(
                        f"CAST({quoted_name} AS TEXT) "
                        "LIKE ? ESCAPE '\\'"
                    )

                where = (
                    " WHERE "
                    + " OR ".join(conditions)
                )

                escaped = (
                    q.replace("\\", "\\\\")
                     .replace("%", "\\%")
                     .replace("_", "\\_")
                )

                parameters = [
                    f"%{escaped}%"
                    for _ in names
                ]

            total = connection.execute(
                f"SELECT COUNT(*) FROM {quoted_table}"
                + where,
                parameters,
            ).fetchone()[0]

            total_pages = max(
                1,
                (total + page_size - 1) // page_size,
            )

            page = min(page, total_pages)
            offset = (page - 1) * page_size

            # Deterministic pagination by primary key where
            # available; otherwise SQLite rowid when supported.
            pk_columns = sorted(
                (
                    column for column in columns
                    if column["pk"]
                ),
                key=lambda column: column["pk"],
            )

            if pk_columns:
                order_by = ", ".join(
                    _quote_identifier(column["name"])
                    for column in pk_columns
                )
            else:
                # Avoid assuming rowid exists on WITHOUT ROWID
                # tables or views.
                order_by = ", ".join(
                    _quote_identifier(name)
                    for name in names
                )

            order_clause = (
                f" ORDER BY {order_by}"
                if order_by else ""
            )

            sql = (
                f"SELECT * FROM {quoted_table}"
                + where
                + order_clause
                + " LIMIT ? OFFSET ?"
            )

            rows = connection.execute(
                sql,
                parameters + [page_size, offset],
            ).fetchall()

            records = [
                [
                    _display_value(row[name])
                    for name in names
                ]
                for row in rows
            ]

        def page_url(target):
            return (
                "/sqlite-viewer?"
                + urlencode({
                    "table": table,
                    "page": target,
                    "page_size": page_size,
                    "q": q,
                })
            )

        return render(
            request,
            "sqlite_viewer.html",
            tables=tables,
            table=table,
            columns=columns,
            names=names,
            records=records,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
            q=q,
            previous_url=page_url(max(1, page - 1)),
            next_url=page_url(min(total_pages, page + 1)),
        )

    finally:
        connection.close()
