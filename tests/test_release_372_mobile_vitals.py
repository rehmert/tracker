from pathlib import Path

from fastapi.testclient import TestClient
from app.main import app

ROOT = Path(__file__).resolve().parents[1]


def test_mobile_vitals_shortcuts():
    with TestClient(app) as client:
        page = client.get('/vitals?events=0')
        assert page.status_code == 200

        for link in (
            '#quick-vitals-entry',
            '#quick-vitals-weight',
            '#quick-vitals-bp',
            '#quick-vitals-pulse'
        ):
            assert f'href="{link}"' in page.text

        assert page.text.count(
            'inputmode="numeric"'
        ) >= 3

        assert 'inputmode="decimal"' in page.text
        assert 'data-tracker-vitals-entry="create"' in page.text
        assert 'type="submit">Save reading' in page.text


def test_vitals_edit_keeps_numeric_inputs():
    source = (
        ROOT / 'app/templates/vitals_edit.html'
    ).read_text()

    assert source.count('inputmode="numeric"') >= 3
    assert 'inputmode="decimal"' in source
    assert 'data-tracker-vitals-entry="edit"' in source
