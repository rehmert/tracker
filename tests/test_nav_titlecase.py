"""Navigation labels use Title Case without changing identifiers."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.templating import nav_title


@pytest.mark.parametrize('source,expected', [
    ('Workflow hub','Workflow Hub'),
    ('Reconstitution calculator','Reconstitution Calculator'),
    ('Inventory tools','Inventory Tools'),
    ('Health & Progress','Health & Progress'),
    ('PK Simulator','PK Simulator'),
    ('FEFO forecast','FEFO Forecast'),
    ('SQLite viewer','SQLite Viewer'),
    ('COAs','COAs'),
    ('Dose Workspace','Dose Workspace'),
])
def test_nav_label(source,expected):
    assert nav_title(source)==expected


def test_sidebar_renders_formatted_labels_and_stable_keys():
    with TestClient(app) as client:
        res=client.get('/')
        assert res.status_code==200

        html=res.text

        for token in (
            '>Workflow Hub</span>',
            '>Reconstitution Calculator</span>',
            '>Inventory Tools</span>',
            '>FEFO Forecast</span>',
            '>SQLite Viewer</span>',
            '>COAs</span>',
            'title="Reconstitution Calculator"',
            'aria-label="Move Reconstitution Calculator up"',
            'data-section="Inventory tools"',
            'data-group="Inventory tools"',
            'data-nav-key="/reconstitution-calculator"',
        ):
            assert token in html, token

        assert '>Reconstitution calculator</span>' not in html
        assert '>Inventory tools</span>' not in html


def test_navigation_preferences_keep_persistent_keys():
    js=(
        Path(__file__).parents[1] /
        'app/static/nav_sort.js'
    ).read_text()

    assert "const STORE='tracker-grouped-nav-v1'" in js
    assert 'sec.dataset.section' in js
    assert "sec.querySelector('.nav-section-toggle span')" in js
