from fastapi.testclient import TestClient
import pytest

from app.main import app
from app.reconstitution_math import calculate


def test_guidance_page_and_explainer_hooks():
    with TestClient(app) as client:
        r=client.get('/reconstitution-calculator')
        assert r.status_code==200

        for marker in (
            'Understanding reconstitution calculations',
            'Total amount, concentration, and liquid volume',
            'Common errors to check',
            'Worked arithmetic example',
            'id="recon-working"',
            'id="recon-working-list"',
            'peptidetracker.ai/calculator/reconstitution',
        ):
            assert marker in r.text


def test_example_matches_calculator():
    result=calculate({
        'kind':'single',
        'method':'target',
        'components':[
            {'name':'Example','amount':5,'unit':'mg'}
        ],
        'volume_ml':2,
        'syringe_ml':1,
        'basis':'0',
        'target_amount':250,
        'target_unit':'mcg',
    })

    assert result['components'][0][
        'concentration'
    ]==pytest.approx(2.5)

    assert result['draw_ml']==pytest.approx(.1)
    assert result['draw_units']==pytest.approx(10)
    assert result['full_draws']==20


def test_no_new_inventory_writes():
    with TestClient(app) as client:
        r=client.get('/reconstitution-calculator')

        assert r.status_code==200
        assert 'Reference arithmetic' in r.text
