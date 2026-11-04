from pathlib import Path
from app.pk_operational221 import status


def test_runtime_status_does_not_publish_sensitive_environment():
    result=status(
        Path('/nonexistent-repo-for-test')
    )

    assert result['code_commit'] is None

    assert not any(
        x in result
        for x in (
            'environment',
            'password',
            'token',
            'backup_path',
            'data_dir'
        )
    )


def test_new_html_assets_exist():
    page=Path('app/templates/pk.html').read_text()

    assert 'pkRuntimeRun' in page
    assert 'pkFastDiagnosticRun' in page
    assert 'tracker-pk-runtime221.js' in page
