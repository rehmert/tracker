"""Regression: read-only Record Explorer handlers release their SQLite handles."""
import sqlite3

import pytest

from app.routers import record_explorer


class TrackedDatabase:
    def __init__(self, raw):
        self.raw = raw
        self.closed = False

    def __getattr__(self, name):
        return getattr(self.raw, name)

    def close(self):
        self.closed = True
        self.raw.close()


@pytest.mark.parametrize("handler", [
    record_explorer.vial_lifecycle,
    record_explorer.notes_history,
])
def test_511_record_explorer_closes_connection(monkeypatch, handler):
    raw = sqlite3.connect(":memory:")
    raw.row_factory = sqlite3.Row
    raw.executescript("""
        CREATE TABLE vials (
            id INTEGER PRIMARY KEY, label TEXT, status TEXT
        );
        INSERT INTO vials VALUES (1,'QA vial','sealed');
        CREATE TABLE pages (
            id INTEGER PRIMARY KEY, title TEXT, body TEXT
        );
        INSERT INTO pages VALUES (1,'QA note','Current');
        CREATE TABLE page_revisions (
            id INTEGER PRIMARY KEY, page_id INTEGER, body TEXT
        );
        INSERT INTO page_revisions VALUES (1,1,'Old');
    """)
    spy = TrackedDatabase(raw)
    monkeypatch.setattr(record_explorer, "database", lambda: spy)
    response = handler()
    assert response.status_code == 200
    assert spy.closed
    with pytest.raises(sqlite3.ProgrammingError):
        raw.execute("SELECT 1")
