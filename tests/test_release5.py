from datetime import date
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool
from app.db import Base
from app.models import Purchase, Supply, SupplyCategory
from app.supply_categories import ensure_categories, validate_supply
from app.routers.health_timeline import RANGES


def test_categories_seed_and_custom_units():
    engine = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        cats = ensure_categories(db)
        assert {'needle', 'syringe', 'empty_vial', 'pen_cartridge', 'bac_water', 'pill'} <= {c.key for c in cats}
        assert validate_supply(db, 'needle', 5).unit == 'count'
        assert validate_supply(db, 'bac_water', 2.5).unit == 'mL'
        db.add(SupplyCategory(key='sharps', label='Sharps containers', unit='count'))
        db.commit()
        assert validate_supply(db, 'sharps', 3).label == 'Sharps containers'


def test_count_unit_rejects_fractional_and_nonfinite():
    import pytest
    engine = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        ensure_categories(db)
        with pytest.raises(ValueError, match='whole number'):
            validate_supply(db, 'needle', 1.5)
        with pytest.raises(ValueError):
            validate_supply(db, 'needle', float('nan'))
        with pytest.raises(ValueError):
            validate_supply(db, 'unknown', 1)


def test_timeline_periods():
    assert 30 in RANGES and 3650 in RANGES
