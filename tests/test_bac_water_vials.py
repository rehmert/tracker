import pytest
from app.bac_water import make_bac_water_supply


def test_bac_water_vials_are_ingredient_free_and_in_ml():
    s = make_bac_water_supply(purchase_id=1, vial_count=10, ml_per_vial=3)
    assert s.kind == 'bac_water'
    assert s.compound_id is None
    assert s.purchased_qty == s.remaining_qty == 30
    assert s.bulk_pack_count == 10
    assert s.bulk_units_per_pack == 3


def test_fractional_volume():
    s = make_bac_water_supply(purchase_id=1, vial_count=2, ml_per_vial=2.5)
    assert s.remaining_qty == 5


@pytest.mark.parametrize('count,volume', [(0,10), (1,0), (-1,10), (1,float('nan')), (1,float('inf'))])
def test_invalid_inputs(count, volume):
    with pytest.raises(ValueError):
        make_bac_water_supply(purchase_id=1, vial_count=count, ml_per_vial=volume)


def test_price_per_vial_preserves_exact_purchase_total():
    from app.services import supply_line_cents
    s = make_bac_water_supply(purchase_id=1, vial_count=10, ml_per_vial=3, price_per_vial_cents=249)
    assert s.purchased_qty == 30
    assert s.bulk_total_cents == 2490
    assert supply_line_cents(s) == 2490

def test_invalid_price_per_vial():
    with pytest.raises(ValueError):
        make_bac_water_supply(purchase_id=1, vial_count=2, ml_per_vial=10, price_per_vial_cents=-1)


def test_bulk_total_line_cost_preserves_exact_cents():
    from app.services import supply_line_cents
    s = make_bac_water_supply(purchase_id=1, vial_count=12, ml_per_vial=10, total_line_cents=2999)
    assert s.bulk_total_cents == 2999
    assert s.purchased_qty == s.remaining_qty == 120
    assert s.compound_id is None
    assert supply_line_cents(s) == 2999


def test_bulk_total_cost_conflict_and_negative_rejected():
    with pytest.raises(ValueError, match='either'):
        make_bac_water_supply(purchase_id=1, vial_count=2, ml_per_vial=10,
                              price_per_vial_cents=100, total_line_cents=200)
    with pytest.raises(ValueError, match='Total line cost'):
        make_bac_water_supply(purchase_id=1, vial_count=2, ml_per_vial=10, total_line_cents=-1)
