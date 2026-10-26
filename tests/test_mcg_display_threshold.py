from app.units import fmt_amount

def test_mass_display_threshold():
    assert fmt_amount(100000, "mass") == "100,000 mcg"
    assert fmt_amount(100001, "mass") == "100.001 mg"
    assert fmt_amount(125000, "mass") == "125 mg"
    assert fmt_amount(-125000, "mass") == "-125 mg"
    assert fmt_amount(2500, "mass") == "2,500 mcg"
    assert fmt_amount(1250000, "mass") == "1.25 g"
    assert fmt_amount(125000, "iu") == "125,000 IU"
