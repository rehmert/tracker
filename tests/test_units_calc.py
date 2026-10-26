from datetime import date, timedelta

import pytest

from app import calc, units as U


def approx(x):
    return pytest.approx(x, rel=1e-9)


def test_convert_mass():
    assert U.convert(5, "mg", "mcg") == 5000
    assert U.convert(250, "mcg", "mg") == 0.25
    assert U.convert(1, "g", "mg") == 1000


def test_convert_refuses_cross_dimension():
    with pytest.raises(U.UnitError):
        U.convert(1, "mg", "IU")
    with pytest.raises(U.UnitError):
        U.convert(1, "mg", "mL")


def test_unit_aliases_and_unknown():
    assert U.parse_unit("ML").name == "mL"
    assert U.parse_unit("ug").name == "mcg"
    with pytest.raises(U.UnitError):
        U.parse_unit("tablespoon")


def test_volume_dose_uses_concentration():
    conc = U.concentration(10_000, 2)  # 10 mg in 2 mL -> 5000 mcg/mL
    assert conc == 5000
    assert U.amount_to_vial_base(0.1, "mL", "mass", conc) == approx(500)
    assert U.amount_to_vial_base(100, "uL", "mass", conc) == approx(500)


def test_volume_dose_needs_volume():
    with pytest.raises(U.UnitError):
        U.amount_to_vial_base(0.1, "mL", "mass", None)


def test_mass_dose_against_iu_vial_refused():
    with pytest.raises(U.UnitError):
        U.amount_to_vial_base(1, "mg", "iu", 100)


def test_formatting():
    assert U.fmt_amount(2_500_000, "mass") == "2.5 g"
    assert U.fmt_amount(2500, "mass") == "2,500 mcg"
    assert U.fmt_amount(250, "mass") == "250 mcg"
    assert U.fmt_amount(10, "iu") == "10 IU"
    assert U.fmt_conc(200_000, "mass") == "200 mg/mL"
    assert U.fmt_amount(None, "mass") == "—"


def test_landed_cost_allocation():
    out = calc.allocate_landed({1: 6000, 2: 4000}, shipping=1000, tax=0, discount=0)
    assert out[1] == approx(6600) and out[2] == approx(4400)
    assert sum(out.values()) == approx(11000)


def test_landed_cost_zero_prices_split_equally():
    out = calc.allocate_landed({1: 0, 2: 0}, shipping=1000, tax=200, discount=0)
    assert out[1] == approx(600) and out[2] == approx(600)


def test_discount_reduces_cost():
    out = calc.allocate_landed({1: 5000}, shipping=0, tax=0, discount=500)
    assert out[1] == approx(4500)


def vial(id, status="in_use", content=10_000, vol=2.0, landed=5000.0, used=0.0):
    return calc.VialData(id, 1, "mass", content, vol, status, landed, used)


def test_vial_remaining_and_cost():
    v = vial(1, used=2_500)
    assert v.remaining_base == 7_500
    assert v.pct_remaining == approx(75)
    assert v.cost_per_base == approx(0.5)
    assert calc.dose_cost_cents(v, 500) == approx(250)
    assert v.remaining_value_cents == approx(3750)


def test_over_logged_vial_clamps():
    v = vial(1, used=12_000)
    assert v.remaining_base == 0 and v.over_base == 2_000


def test_compound_ref_weighted_price_and_inventory():
    a = vial(1, content=10_000, landed=5_000, used=10_000, status="finished")
    b = vial(2, content=10_000, landed=6_000, used=1_000)
    c = vial(3, status="sealed", content=10_000, vol=None, landed=4_000)
    ref = calc.build_compound_ref(1, "X", [a, b, c], logged_28d_base=2_800)
    assert ref.on_hand_base == 9_000 + 10_000
    assert ref.cost_per_base == approx((6_000 + 4_000) / 20_000)  # finished excluded
    assert ref.conc_per_ml == approx(5_000)                       # from in-use vial
    assert ref.typical_vial_base == 10_000 and ref.typical_vial_cents == 4_000
    assert ref.actual_per_week_base == approx(700)


def test_project_item_basics():
    ref = calc.build_compound_ref(1, "X", [vial(1, landed=5000)])
    item = calc.ItemInput(1, 250, "mcg", 5, "week")
    r = calc.project_item(item, ref, horizon_days=84, today=date(2026, 1, 1))
    assert r.ok
    assert r.per_week_base == approx(1250)
    assert r.cost_per_dose == approx(125)
    assert r.cost_per_week == approx(625)
    assert r.horizon_need_base == approx(1250 * 12)
    assert r.draw_ml == approx(0.05) and r.syringe_marks == approx(5)
    assert r.days_supply == approx(10_000 / (1250 / 7))
    assert r.runout == date(2026, 1, 1) + timedelta(days=56)
    assert r.shortfall_base == approx(15_000 - 10_000)
    assert r.vials_to_buy == 1 and r.buy_cents == approx(5000)


def test_project_item_volume_dose_and_interval():
    ref = calc.build_compound_ref(1, "X", [vial(1)])
    r = calc.project_item(calc.ItemInput(1, 0.1, "mL", 3, "interval"), ref, 30)
    assert r.dose_base == approx(500)
    assert r.doses_per_day == approx(1 / 3)


def test_changing_frequency_scales_cost_and_runout():
    ref = calc.build_compound_ref(1, "X", [vial(1)])
    a = calc.project_item(calc.ItemInput(1, 100, "mcg", 2, "week"), ref, 84)
    b = calc.project_item(calc.ItemInput(1, 100, "mcg", 4, "week"), ref, 84)
    assert b.cost_per_month == approx(2 * a.cost_per_month)
    assert b.days_supply == approx(a.days_supply / 2)


def test_project_item_warnings():
    ref = calc.build_compound_ref(1, "X", [vial(1, vol=None)])
    r = calc.project_item(calc.ItemInput(1, 0.1, "mL", 1, "day"), ref, 30)
    assert not r.ok and r.warnings
    r = calc.project_item(calc.ItemInput(1, 1, "mcg", 1, "interval"), ref, 30)
    assert r.ok
    r = calc.project_item(calc.ItemInput(1, 1, "mcg", 0, "interval"), ref, 30)
    assert not r.ok
    empty = calc.build_compound_ref(2, "Y", [])
    r = calc.project_item(calc.ItemInput(2, 1, "mg", 1, "week"), empty, 30)
    assert r.ok and r.cost_per_week is None and r.warnings


def test_iu_vial():
    v = calc.VialData(1, 1, "iu", 5000, 5.0, "in_use", 4000.0)
    ref = calc.build_compound_ref(1, "H", [v])
    r = calc.project_item(calc.ItemInput(1, 500, "IU", 2, "week"), ref, 28)
    assert r.dim == "iu" and r.per_week_base == 1000
    bad = calc.project_item(calc.ItemInput(1, 1, "mg", 2, "week"), ref, 28)
    assert not bad.ok


def test_totals():
    ref = calc.build_compound_ref(1, "X", [vial(1)])
    rs = [calc.project_item(calc.ItemInput(1, 100, "mcg", 7, "week"), ref, 28)] * 2
    t = calc.totals(rs)
    assert t["week"] == approx(2 * 700 * 0.5)
