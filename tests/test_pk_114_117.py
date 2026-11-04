from pathlib import Path


def test_duplicate_and_history_routes():
    text=Path('app/routers/pk.py').read_text()

    assert (
        '@router.post("/scenarios/{sid}/duplicate"'
        in text
    )

    assert (
        '@router.get("/scenarios/{sid}/change-history")'
        in text
    )

    js=Path(
        'app/static/js/tracker-pk-extras117.js'
    ).read_text()

    assert 'tracker-pk-scenario-template-v1' in js
