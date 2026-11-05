import json
from app.pk_manifest269 import report,write_atomic


def test_manifest_is_bounded_and_root_private(tmp_path):
    log=tmp_path/'release.test'/'deployment.log'
    log.parent.mkdir()

    log.write_text(
        'Started: 2026-11-04T10:00:00; instance: DEV\n'
        'EXIT_STATUS=0\n'
        'SECRET=must-not-leak\n'
    )

    payload=report(tmp_path)

    assert payload['successes']==1
    assert payload['count']==1
    assert 'SECRET' not in json.dumps(payload)

    dest=write_atomic(
        tmp_path,
        tmp_path/'manifest.json'
    )

    assert dest.stat().st_mode & 0o777==0o600

    assert json.loads(
        dest.read_text()
    )['successes']==1
