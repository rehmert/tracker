from pathlib import Path


def test_sensitivity_uses_existing_pk_model():
    source=Path(
        'app/pk_sensitivity169.py'
    ).read_text()
    assert 'pk.series(' in source
    assert '(.75,1.0,1.25)' in source
    assert 'step_hours=resolution(' in source


def test_sensitivity_ui_present():
    html=Path(
        'app/templates/pk.html'
    ).read_text()
    assert 'id="pkSensitivityPlot"' in html
    assert 'id="pkSensitivityExport"' in html
