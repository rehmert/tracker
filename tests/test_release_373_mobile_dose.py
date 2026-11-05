from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app
from tests.test_stage17_dose_blend_integrity import seed_vials

ROOT = Path(__file__).resolve().parents[1]


def test_mobile_dose_form_preserves_recording_guards():
    seed_vials('MobileLog-' + str(uuid4()), 1)

    with TestClient(app) as client:
        response = client.get('/doses')
        assert response.status_code == 200
        html = response.text

        for href in (
            '#calendar-vial-picker',
            '#tracker-dose-final-review',
            '#tracker-dose-submit-373',
            '/vitals#quick-vitals-entry'
        ):
            assert f'href="{href}"' in html

        assert 'hx-post="/doses"' in html
        assert 'submission_token' in html
        assert 'id="tracker-dose-final-review"' in html
        assert 'id="tracker-dose-submit-373"' in html
        assert 'inputmode="decimal"' in html


def test_large_tap_targets_and_edit_parity():
    css = (
        ROOT / 'app/static/css/tracker-mobile-log373.css'
    ).read_text()

    assert 'min-height: 56px' in css
    assert '.tracker-time24-controls' in css
    assert '@media (max-width: 720px)' in css

    edit = (
        ROOT / 'app/templates/dose_edit.html'
    ).read_text()

    assert 'tracker-time24-371.js' in edit
    assert 'inputmode="decimal"' in edit
