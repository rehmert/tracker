from app import units
from app.models import Coa, CoaRevision
from app.routers.coas import _snapshot, _revision, COA_STATUSES
from app.templating import signed_decimal, templates
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from app.db import Base
from app.migrations import migrate


def test_plain_decimal_formatting():
    assert units._num(0.00000012) == '0.00000012'
    assert signed_decimal(0.000012) == '+0.000012'
    assert "%.4g" not in templates.env.loader.get_source(templates.env, 'inventory_intelligence.html')[0]


def test_coa_review_history_and_schema(tmp_path):
    engine = create_engine(f'sqlite:///{tmp_path / "coa.sqlite"}')
    Base.metadata.create_all(engine)
    migrate(engine)
    with Session(engine) as db:
        c = Coa(original_name='certificate.pdf', stored_name='test-unique.pdf', lab_name='Lab A',
                purity_pct=99.2, verification_status='unreviewed')
        db.add(c)
        db.commit()
        assert 'verified' in COA_STATUSES
        before = _snapshot(c)
        _revision(db, c, 'verification')
        c.verification_status = 'verified'
        c.verification_notes = 'Reviewed against report'
        db.commit()
        history = db.query(CoaRevision).filter_by(coa_id=c.id).one()
        assert '"verification_status": "unreviewed"' in history.snapshot_json
        assert before['purity_pct'] == 99.2
    engine.dispose()
