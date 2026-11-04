from app.pk_release_report253 import collect


def test_structured_report_parsing(tmp_path):
    good=tmp_path/'release.good'
    good.mkdir()

    (good/'deployment.log').write_text(
        'Started: 2026-11-04T12:00:00; instance: DEV\n'
        'EXIT_STATUS=0\n'
    )

    bad=tmp_path/'release.bad'
    bad.mkdir()

    (bad/'deployment.log').write_text(
        'Started: 2026-11-04T13:00:00; instance: PROD\n'
        'EXIT_STATUS=1\n'
    )

    data=collect(tmp_path)

    assert data['format']=='tracker-release-history-v1'
    assert len(data['entries'])==2
    assert {
        x['status'] for x in data['entries']
    }=={'success','failed'}

    assert all(
        set(x)=={'started','instance','status'}
        for x in data['entries']
    )
