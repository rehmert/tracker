"""Release 379: weekly nutrient data and target validation."""

import csv
import io

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.pool import StaticPool

from app.routers import food, food_week379


@pytest.fixture
def setup(monkeypatch):
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    monkeypatch.setattr(food, "engine", engine)

    app = FastAPI()
    app.include_router(food.router)
    app.include_router(food_week379.router)

    with TestClient(app) as client:
        yield client, engine

    engine.dispose()


def add(client, day, protein=None, sodium=None):
    data = {
        "day": day,
        "name": "Test Food",
        "serving_description": "1 serving",
        "servings": "1",
        "meal": "Breakfast",
        "energy": "100",
    }

    if protein is not None:
        data["proteins"] = str(protein)

    if sodium is not None:
        data["sodium"] = str(sodium)

    result = client.post(
        "/food/entry",
        data=data,
        follow_redirects=False,
    )

    assert result.status_code == 303


def test_weekly_coverage_and_targets(setup):
    client, engine = setup

    add(client, "2026-11-04", protein=20, sodium=0)
    add(client, "2026-11-04", protein=None, sodium=40)
    add(client, "2026-11-05", protein=30, sodium=100)

    with engine.begin() as db:
        db.execute(text("""
            INSERT INTO tracker_food_targets(nutrient,value)
            VALUES ('proteins', 25)
        """))

    review = food_week379.week_details("2026-11-05")
    assert len(review["days"]) == 7

    protein = next(
        item for item in review["nutrients"]
        if item["key"] == "proteins"
    )

    assert protein["logged_days"] == 2
    assert protein["observed_days"] == 2
    assert protein["complete_days"] == 1
    assert protein["complete_average"] == 30
    assert protein["below"] == 0
    assert protein["above"] == 1

    sodium = next(
        item for item in review["nutrients"]
        if item["key"] == "sodium"
    )

    assert sodium["complete_days"] == 2
    assert sodium["complete_average"] == 70


def test_unknown_is_not_zero(setup):
    client, engine = setup

    add(client, "2026-11-05", protein=None)

    review = food_week379.week_details("2026-11-05")
    protein = next(
        item for item in review["nutrients"]
        if item["key"] == "proteins"
    )

    assert protein["logged_days"] == 1
    assert protein["complete_days"] == 0
    assert protein["observed_average"] is None
    assert protein["complete_average"] is None


def test_target_validation_is_atomic(setup):
    client, engine = setup
    food.init_food_schema()

    with engine.begin() as db:
        db.execute(text("""
            INSERT INTO tracker_food_targets(nutrient,value)
            VALUES ('proteins', 120)
        """))

    for bad in ("-1", "nan", "invalid", "100001"):
        response = client.post(
            "/food/targets",
            data={
                "day": "2026-11-05",
                "proteins": "130",
                "sodium": bad,
            },
            follow_redirects=False,
        )

        assert response.status_code == 422

        with engine.connect() as db:
            value = db.execute(text("""
                SELECT value FROM tracker_food_targets
                WHERE nutrient='proteins'
            """)).scalar_one()

        assert value == 120

    good = client.post(
        "/food/targets",
        data={
            "day": "2026-11-05",
            "proteins": "140",
            "sodium": "0",
        },
        follow_redirects=False,
    )

    assert good.status_code == 303

    with engine.connect() as db:
        values = dict(db.execute(text("""
            SELECT nutrient,value FROM tracker_food_targets
        """)).all())

    assert values["proteins"] == 140
    assert values["sodium"] == 0


def test_weekly_csv_preserves_unknown(setup):
    client, engine = setup
    add(client, "2026-11-05", protein=None, sodium=0)

    response = client.get(
        "/food/weekly.csv?day=2026-11-05"
    )

    assert response.status_code == 200
    assert response.content.startswith(b"\xef\xbb\xbf")

    rows = list(csv.DictReader(io.StringIO(
        response.text.lstrip("\ufeff")
    )))

    assert len(rows) == 7
    last = rows[-1]

    assert last["Date"] == "2026-11-05"
    assert last["Protein (g)"] == ""
    assert last["Protein Reported Foods"] == "0"
    assert last["Protein Complete"] == "no"
    assert last["Sodium (mg)"] == "0.0"
    assert last["Sodium Complete"] == "yes"


def test_invalid_weekly_date(setup):
    client, engine = setup

    response = client.get(
        "/food/weekly.csv?day=not-a-date"
    )

    assert response.status_code == 422
