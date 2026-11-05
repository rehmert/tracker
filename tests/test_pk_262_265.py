from pathlib import Path
from jinja2 import Environment


def test_client_load_order_and_csrf():
    html=Path(
        'app/templates/pk.html'
    ).read_text()

    js=Path(
        'app/static/js/tracker-pk-client265.js'
    ).read_text()

    revisions=Path(
        'app/static/js/tracker-pk-revisions229.js'
    ).read_text()

    assert (
        html.index('tracker-pk-client265.js')
        <html.index('tracker-pk-revisions229.js')
    )

    assert 'trackerCsrfToken' in js
    assert "credentials:'same-origin'" in js
    assert 'trackerPkClient265.request' in revisions

    Environment().parse(html)
