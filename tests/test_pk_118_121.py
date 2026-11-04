from pathlib import Path


def test_zoom_and_export():
    html=Path('app/templates/pk.html').read_text()

    code=Path(
        'app/static/js/tracker-pk-graph121.js'
    ).read_text()

    assert 'id="pkZoomIn"' in html
    assert 'id="pkExportAnalysis"' in html
    assert 'tracker-pk-analysis-v1' in code
