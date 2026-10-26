from app import units as U
from app.templating import num, n0, n1, signed, num_input, templates

def test_grouped_numbers_and_small_values():
    assert U._num(1234567.89, 9) == "1,234,567.89"
    assert U._num(0.000125, 4) == "0.000125"
    assert U._num(125000, 4) == "125,000"
    assert num(1234567.89, 9) == "1,234,567.89"
    assert n0(1234567) == "1,234,567"
    assert n1(12345.6) == "12,345.6"
    assert signed(-12345.6) == "-12,345.6"
    assert num_input(1234567.89, 9) == "1234567.89"
    assert templates.env.filters["num_input"](12345) == "12345"

def test_unit_displays_grouped():
    assert U.fmt_amount(125000000, "iu") == "125,000,000 IU"
    assert U.fmt_conc(125000000, "iu") == "125,000,000 IU/mL"
