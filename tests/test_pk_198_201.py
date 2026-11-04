from pathlib import Path
from jinja2 import Environment


def test_navigation_buttons_target_real_sections():
    page=Path('app/templates/pk.html').read_text()
    script=Path(
        'app/static/js/tracker-pk-panels201.js'
    ).read_text()

    for target in (
        'pkSetup',
        'pkResults',
        'pkSensitivityWorkspace',
        'pkDeltaCard',
        'pkScenarioLibraryAnchor'
    ):
        assert f'id="{target}"' in page
        assert f"'{target}'" in script

    assert 'aria-pressed' in script
    Environment().parse(page)
