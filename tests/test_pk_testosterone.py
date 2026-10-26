from app.pk import profile

def test_testosterone_variants():
    assert profile("Testosterone") == (192.0, 24.0)
    assert profile("Testosterone Cypionate 250 mg/mL") == (192.0, 24.0)
    assert profile("Testosterone Enanthate 200 mg") == (120.0, 24.0)
    assert profile("TRT") == (192.0, 24.0)
    assert profile("Testosterone gel") is None
    assert profile("Testosterone propionate") is None
