from pathlib import Path
from jinja2 import Environment

def test_workspace_navigation_targets():
    html=Path('app/templates/pk.html').read_text()
    js=Path('app/static/js/tracker-pk-workspace185.js').read_text()
    for ident in ['pkSetup','pkResults','pkSensitivityWorkspace','pkDeltaCard','pkScenarioLibraryAnchor']:
        assert f'id="{ident}"' in html
        assert ident in js
    Environment().parse(html)
