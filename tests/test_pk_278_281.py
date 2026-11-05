from pathlib import Path


def test_read_only_browser_smoke_contract():
    source=Path(
        'tests/browser/test_pk_smoke_281.py'
    ).read_text()

    assert "BASE+'/pk'" in source
    assert '#pkRevisionLoad' in source
    assert '#pkGrid217Run' in source
    assert '.click(' not in source
    assert '.fill(' not in source

    script=Path(
        'scripts/tracker-pk-browser-check281.sh'
    ).read_text()

    assert 'test_pk_smoke_281.py' in script
