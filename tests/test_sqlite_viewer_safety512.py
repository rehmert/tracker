"""Release 512: SQLite viewer CSV is safe and releases read-only handles.

All fixtures use their own temporary SQLite file. No live application
database, credentials, or service is accessed.
"""
import csv
import io
import sqlite3

import pytest
from fastapi import HTTPException

from app import config
from app.routers import sqlite_viewer


@pytest.fixture
def isolated_sqlite(tmp_path, monkeypatch):
    file = tmp_path / "sqlite-viewer512.db"
    records = (
        ("=HYPERLINK(\"https://invalid.test\",\"x\")", "formula"),
        (" \t=SUM(1,2)", "formula with whitespace"),
        ("\t@SUM(1,2)", "formula with tab"),
        ("\n+SUM(1,2)", "formula with newline"),
        (" -SUM(1,2)", "formula with minus"),
        ("Normal safe text", "normal"),
        ("ordinary = text", "ordinary"),
    )
    with sqlite3.connect(file) as db:
        db.execute(
            "CREATE TABLE compounds("
            "id INTEGER PRIMARY KEY, name TEXT,"
            "category TEXT, primary_unit TEXT)"
        )
        db.executemany(
            "INSERT INTO compounds(name, category, primary_unit) "
            "VALUES (?, ?, 'mg')",
            records,
        )

    monkeypatch.setattr(config, "DB_URL", f"sqlite:///{file}")
    return records


def test_512_sqlite_csv_escapes_whitespace_prefixed_formulas(isolated_sqlite):
    response = sqlite_viewer.sqlite_viewer_export("compounds")
    assert response.status_code == 200
    parsed = list(csv.DictReader(io.StringIO(response.body.decode("utf-8"))))
    assert len(parsed) == len(isolated_sqlite)
    for actual, (raw, label) in zip(parsed, isolated_sqlite):
        if label.startswith("formula"):
            assert actual["name"] == "'" + raw
        else:
            assert actual["name"] == raw


@pytest.mark.parametrize("table,expected_status", [
    ("compounds", 200),
    ("missing_table", 404),
])
def test_512_export_closes_sqlite_handle_even_on_error(
    isolated_sqlite, monkeypatch, table, expected_status
):
    opened = []
    original = sqlite_viewer._connection

    def record_connection():
        connection = original()
        opened.append(connection)
        return connection

    monkeypatch.setattr(sqlite_viewer, "_connection", record_connection)
    if expected_status == 200:
        assert sqlite_viewer.sqlite_viewer_export(table).status_code == 200
    else:
        with pytest.raises(HTTPException) as raised:
            sqlite_viewer.sqlite_viewer_export(table)
        assert raised.value.status_code == expected_status

    assert len(opened) == 1
    with pytest.raises(sqlite3.ProgrammingError):
        opened[0].execute("SELECT 1")


def test_512_failed_readonly_setup_closes_connection(isolated_sqlite, monkeypatch):
    class FailedConnection:
        closed = False

        def execute(self, statement):
            raise sqlite3.OperationalError("Query-only setup failed")

        def close(self):
            self.closed = True

    failure = FailedConnection()
    monkeypatch.setattr(
        sqlite_viewer.sqlite3, "connect",
        lambda *args, **kwargs: failure,
    )
    with pytest.raises(sqlite3.OperationalError):
        sqlite_viewer._connection()
    assert failure.closed
