"""Replenishment classification and real HTTP tests."""

from datetime import date
from fastapi.testclient import TestClient

from app.main import app
from app.routers.replenishment_review import build_worklist


def sample(stock=8, demand=3, shortage=0, review=False):
    return {
        "compound": "Example",
        "unit": "mg",
        "dated_stock": stock,
        "unknown_stock": 0,
        "expired_existing": 0,
        "incomplete": review,
        "horizons": {
            28: {
                "demand": demand,
                "consumed": demand - shortage,
                "shortage": shortage,
                "expired": 0,
                "remaining": max(0, stock - demand),
                "first_shortage":
                    date(2026, 11, 13) if shortage else None,
            }
        },
    }


def history(remaining=8000, days=35):
    return {
        "name": "Example",
        "unit": "mcg",
        "remaining": remaining,
        "days_left": days,
        "depletion":
            None if days is None else date(2026, 12, 7),
        "used": 0 if days is None else 1000,
    }


def test_scheduled_shortfall():
    row = build_worklist(
        [sample(stock=2, demand=5, shortage=3)],
        [history()], [], {"example": 7},
    )[0]
    assert row["status"] == "shortfall"
    assert row["shortage"] == 3
    assert row["id"] == 7
    assert row["first_shortage"] == date(2026, 11, 13)


def test_depleted_inventory_without_fefo():
    row = build_worklist(
        [], [history(remaining=0, days=None)],
        [], {"example": 7},
    )[0]
    assert row["status"] == "depleted"
    assert row["remaining"] == 0


def test_depleted_scheduled_inventory():
    row = build_worklist(
        [sample(stock=0, demand=3, shortage=3)],
        [], [], {"example": 7},
    )[0]
    assert row["status"] == "depleted"
    assert row["shortage"] == 3


def test_historical_depletion():
    row = build_worklist(
        [sample()], [history(days=12)],
        [], {"example": 7},
    )[0]
    assert row["status"] == "near-term"
    assert row["shortage"] == 0


def test_incomplete_schedule_review():
    row = build_worklist(
        [sample(review=True)],
        [history(days=12)],
        [], {"example": 7},
    )[0]
    assert row["status"] == "review"
    assert row["incomplete"]


def test_missing_history_has_no_estimated_date():
    row = build_worklist(
        [sample()], [history(days=None)],
        [], {"example": 7},
    )[0]
    assert row["status"] == "no-history"
    assert row["depletion"] is None


def test_supplies_and_empty_stock():
    supplies = [
        {
            "id": 2, "name": "Syringe",
            "remaining": 0, "days_left": None,
            "depletion": None,
        },
        {
            "id": 3, "name": "Needle",
            "remaining": 20, "days_left": None,
            "depletion": None,
        },
    ]
    rows = build_worklist([], [], supplies, {})
    assert [r["status"] for r in rows] == [
        "depleted", "no-history",
    ]


def test_http_routes_with_isolated_database():
    with TestClient(app) as client:
        paths = [
            "/replenishment-review",
            "/replenishment-review?horizon=14&history=30",
            "/replenishment-review?horizon=111&history=15",
            "/replenishment-review.csv?category=all",
        ]
        for path in paths:
            response = client.get(path)
            assert response.status_code == 200, (
                path, response.text[:300]
            )

        page = client.get("/replenishment-review")
        assert "Replenishment review" in page.text

        csv_response = client.get("/replenishment-review.csv")
        assert "text/csv" in csv_response.headers["content-type"]
