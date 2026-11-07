"""Release 470 private SQLAlchemy migrations."""

from pathlib import Path
import pytest

from app.secondary_food_inventory_orm470 import (
    FOOD_ENTRIES470,
    INVENTORY_COMPOUNDS470,
    INVENTORY_VIALS470,
    WATER_TOTAL470,
)


def test_orm470_queries_are_bounded_and_allowlisted():
    for query in (
        FOOD_ENTRIES470,
        INVENTORY_COMPOUNDS470,
        INVENTORY_VIALS470,
        WATER_TOTAL470,
    ):
        sql = str(query).upper()
        assert "SELECT " in sql
        assert "INSERT " not in sql
        assert "UPDATE " not in sql
        assert "DELETE " not in sql

    assert "LIMIT :limit" in str(FOOD_ENTRIES470)
    assert "LIMIT 200" in str(INVENTORY_COMPOUNDS470)
    assert "LIMIT 200" in str(INVENTORY_VIALS470)


def test_orm470_no_global_database_access():
    source = Path(
        "app/secondary_food_inventory_orm470.py"
    ).read_text()

    assert "private_orm468(request)" in source
    assert "validate_response454(" in source
    assert "_safe_number452(" in source

    for forbidden in (
        "from .db import engine",
        "from .db import SessionLocal",
        "sqlite3.connect(",
        "subprocess.run(",
        "request.query_params",
        "request.path_params",
        "set_cookie(",
    ):
        assert forbidden not in source


def test_orm470_real_routes_are_migrated():
    source = Path(
        "app/secondary_preview430.py"
    ).read_text()

    assert source.count(
        "report = private_inventory_orm470(request)"
    ) == 1

    assert source.count(
        "report = private_food_day_orm470(request, day)"
    ) == 1

    assert source.count(
        "reports = private_food_week_orm470(request, ending)"
    ) == 2

    # Do not remove write-worker functionality.
    assert "request_inventory435(" in source
    assert "request_write456(" in source


def test_orm470_invalid_date_rejected():
    from app.worker_food452 import validate_day452

    for invalid in (
        "2026-02-30",
        "2026-01-01 OR 1=1",
        "not-a-date",
        "",
    ):
        with pytest.raises(ValueError):
            validate_day452(invalid)
