from pathlib import Path


def test_report_api_and_interface():
    router=Path('app/routers/pk.py').read_text()
    html=Path('app/templates/pk.html').read_text()
    assert '/workspace/{sid}/report' in router
    assert 'tracker-pk-report-v1' in router
    assert 'id="pkReportDownload"' in html


def test_guarded_release_exists():
    script=Path(
        'scripts/tracker-release.sh'
    ).read_text()
    assert 'PROD requires promoted main' in script
    assert 'restore' in script.lower()
    assert 'pre-deployment' in script
