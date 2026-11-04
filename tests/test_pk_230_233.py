from pathlib import Path
from jinja2 import Environment


def test_visible_layers_have_matching_controls():
    html=Path('app/templates/pk.html').read_text()
    js=Path('app/static/pk.js').read_text()
    graph=Path('app/static/js/tracker-pk-graph137.js').read_text()
    for ident in ('pkLayerRecorded','pkLayerPlanned','pkLayerMarkers'):
        assert f'id="{ident}"' in html
    assert 'pkLayerRecorded' in js
    assert 'pkLayerPlanned' in js
    assert 'pkLayerMarkers' in graph
    Environment().parse(html)
