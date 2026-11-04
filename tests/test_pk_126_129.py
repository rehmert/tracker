from pathlib import Path
from app.pk_scenario_version import version


def test_canonical_revision():
    assert version({'a':1,'b':2})==version(
        {'b':2,'a':1}
    )


def test_reload_and_audit_contract():
    js=Path(
        'app/static/js/tracker-pk-tools125.js'
    ).read_text()

    assert 'window.trackerPkReloadScenario' in js

    routes=Path('app/routers/pk.py').read_text()

    for name in (
        'scenario_create',
        'scenario_update',
        'scenario_delete',
        'dose_add',
        'dose_update',
        'dose_delete'
    ):
        assert f'"{name}"' in routes
