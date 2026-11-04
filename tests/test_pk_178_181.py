from app.pk_metrics181 import resolution,metrics

def test_short_half_life_sampling():
    assert resolution(.18333)==.5
    assert resolution(12)==1
    assert resolution(120)==12

def test_trapezoid_not_sample_average():
    rows=[
        {'at':'2026-11-04T00:00:00','planned':0},
        {'at':'2026-11-04T01:00:00','planned':10},
        {'at':'2026-11-04T04:00:00','planned':10}
    ]
    out=metrics(rows)
    assert out['auc']==35
    assert out['mean']==8.75
