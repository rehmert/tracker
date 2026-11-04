from datetime import datetime
from pathlib import Path

from app.pk_template_import import (
    Template,TemplateDose
)


def test_template_validation():
    data=Template(
        format='tracker-pk-scenario-template-v1',
        compound_id=1,
        compound_name='Example',
        name='Test',
        half_life_hours=120,
        absorption_half_life_hours=12,
        doses=[
            TemplateDose(
                planned_at=datetime(2026,11,4,8),
                amount_mg=2
            )
        ]
    )

    assert len(data.doses)==1


def test_import_preview_contract():
    routes=Path(
        'app/routers/pk.py'
    ).read_text()

    html=Path(
        'app/templates/pk.html'
    ).read_text()

    assert '/scenarios/import-preview' in routes
    assert 'id="pkImportConfirm"' in html
    assert 'id="pkLibraryStatus" role="status"' in html
