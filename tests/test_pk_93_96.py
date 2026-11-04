from pathlib import Path
from app.pk_analysis_93 import metrics


def test_trapezoidal_auc():
    result = metrics(
        [
            '2026-11-04T00:00:00',
            '2026-11-04T02:00:00',
        ],
        [0, 4],
    )
    assert result['auc_mg_equivalent_hours'] == 4
    assert result['mean_mg_equivalent'] == 2


def test_revision_and_json_controls():
    html = Path(
        'app/templates/protocol_edit.html'
    ).read_text()

    assert 'id="pkExpComparePrevious"' in html
    assert 'id="pkExpReportJson"' in html
    assert 'tracker-pk-report96.js?v=bundle96' in html
