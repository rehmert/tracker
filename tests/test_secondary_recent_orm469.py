"""Release 469: private SQLAlchemy migration contracts."""

from pathlib import Path

import pytest

from app.secondary_recent_orm469 import (
    ACTIONS469,
    FIELDS469,
    QUERIES469,
    read_recent_orm469,
)


def test_recent_orm469_allowlisted_queries():
    assert ACTIONS469 == frozenset({
        "vitals", "doses"
    })
    assert set(QUERIES469) == set(ACTIONS469)
    assert set(FIELDS469) == set(ACTIONS469)

    for query in QUERIES469.values():
        assert "LIMIT 10" in str(query)
        assert "SELECT " in str(query)
        assert "INSERT " not in str(query)
        assert "UPDATE " not in str(query)
        assert "DELETE " not in str(query)


def test_recent_orm469_rejects_arbitrary_action():
    for invalid in (
        "users",
        "admin",
        "sql",
        "",
        3,
        None,
        ["vitals"],
    ):
        with pytest.raises(ValueError):
            read_recent_orm469(None, invalid)


def test_recent_orm469_no_global_db_access():
    source = Path(
        "app/secondary_recent_orm469.py"
    ).read_text()

    assert "private_orm468(request)" in source
    assert "QUERIES469[kind]" in source

    for forbidden in (
        "from .db import engine",
        "from .db import SessionLocal",
        "request.query_params",
        "request.path_params",
        "user_id=request",
        "sqlite3.connect(",
        "subprocess.run(",
        "set_cookie(",
    ):
        assert forbidden not in source, forbidden


def test_recent_orm469_existing_routes_wired():
    source = Path(
        "app/secondary_preview430.py"
    ).read_text()

    start = source.index(
        "def _recent_page432(request, kind):"
    )
    end = source.index(
        '@preview_app.get("/vitals")', start
    )
    section = source[start:end]

    assert (
        "report = read_recent_orm469(request, kind)"
        in section
    )

    assert "report = read_recent432(uid, kind)" not in section

    assert (
        "private-recent-orm469" in section
    )

    # The original worker remains available for consumers
    # outside these two migrated HTTP pages.
    assert Path("app/worker_recent432.py").exists()
