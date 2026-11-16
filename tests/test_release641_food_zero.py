"""Release 641: zero-default migration must be complete, atomic and idempotent."""
import importlib.util
import json
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.pool import StaticPool

from app.routers import food, food_bundle376

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/tracker-food-zero641.py"
spec = importlib.util.spec_from_file_location("food_zero641", SCRIPT)
zero = importlib.util.module_from_spec(spec)
spec.loader.exec_module(zero)


@pytest.fixture
def db_engine():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False},
                           poolclass=StaticPool)
    food_bundle376.init_schema(engine)
    yield engine
    engine.dispose()


def add(db_engine, nutrients):
    with db_engine.begin() as db:
        return db.execute(text("""
            INSERT INTO tracker_food_products
                (name, serving_description, nutrients, barcode, source)
            VALUES ('Test', '1 serving', :nutrients, '', 'manual')
        """), {"nutrients": json.dumps(nutrients)}).lastrowid


def get(db_engine, product_id):
    with db_engine.connect() as db:
        return json.loads(db.execute(text("""
            SELECT nutrients FROM tracker_food_products WHERE id=:id
        """), {"id": product_id}).scalar_one())


def test_641_all_missing_and_explicit_unknowns_become_numeric_zero(db_engine):
    row = add(db_engine, {
        "energy": 100, "proteins": 8.5, "sodium": None,
        "potassium": "UNKNOWN", "magnesium": "null",
        "vitamin-d": "", "custom_provenance": "user supplied",
    })
    dry = zero.normalize_saved_foods641(db_engine)
    assert dry == {"examined": 1, "changed": 1, "executed": False}
    assert get(db_engine, row)["sodium"] is None
    result = zero.normalize_saved_foods641(db_engine, execute=True)
    assert result["changed"] == 1
    saved = get(db_engine, row)
    assert set(food.NUTRIENTS) <= set(saved)
    assert all(type(saved[key]) in (int, float) for key in food.NUTRIENTS)
    assert saved["energy"] == 100 and saved["proteins"] == 8.5
    assert saved["custom_provenance"] == "user supplied"
    assert saved["sodium"] == 0.0 and saved["potassium"] == 0.0
    assert zero.normalize_saved_foods641(db_engine, execute=True)["changed"] == 0


def test_641_backfill_fails_all_or_nothing_on_bad_legacy_payload(db_engine):
    one = add(db_engine, {"energy": 100, "potassium": None})
    two = add(db_engine, {"energy": -3})
    with pytest.raises(ValueError, match="Invalid numeric"):
        zero.normalize_saved_foods641(db_engine, execute=True)
    assert get(db_engine, one)["potassium"] is None
    assert get(db_engine, two)["energy"] == -3


def test_641_backfill_preserves_legitimate_numeric_strings(db_engine):
    pk = add(db_engine, {"energy": "100", "proteins": 0,
                         "magnesium": "not reported"})
    zero.normalize_saved_foods641(db_engine, execute=True)
    saved = get(db_engine, pk)
    assert saved["energy"] == "100"
    assert saved["proteins"] == 0
    assert saved["magnesium"] == 0.0


def test_641_invalid_unknown_is_not_silently_zeroed():
    with pytest.raises(ValueError, match="Unrecognized"):
        zero.normalize_row641(json.dumps({"energy": "unverified value"}))
