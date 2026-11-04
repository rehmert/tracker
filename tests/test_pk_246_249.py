from pathlib import Path
from jinja2 import Environment


def test_revision_ui_and_workspace_contracts():
    js=Path(
        'app/static/js/tracker-pk-revisions229.js'
    ).read_text()

    assert 'requestGeneration' in js
    assert 'data.added' in js
    assert 'data.removed' in js

    nav=Path(
        'app/static/js/tracker-pk-workspace185.js'
    ).read_text()

    assert 'bar.hidden=true' in nav

    Environment().parse(
        Path('app/templates/pk.html').read_text()
    )
