from pathlib import Path
from app.pk_scenario_ops import fingerprint


def test_empty_version_is_stable():
    assert fingerprint([])==fingerprint([])


def test_undo_and_scoping_contracts():
    api=Path('app/pk_scenario_ops.py').read_text()
    routes=Path('app/routers/pk.py').read_text()

    assert 'expected_version' in api
    assert "audit.action='bulk_restored'" in api
    assert 'PkPlannedDose.scenario_id==sid' in api

    assert (
        '@router.post("/scenarios/{sid}/doses/undo-delete")'
        in routes
    )
