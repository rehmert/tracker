from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db import Base
from app.models import Compound,Vial
from app.list_queries297 import vial_listing,purchase_listing


def test_vial_filtering_happens_in_sql(tmp_path):
    engine=create_engine(
        f'sqlite:///{tmp_path / "lists.db"}'
    )

    Base.metadata.create_all(engine)

    with Session(engine) as db:
        compound=Compound(name='ListTest')
        db.add(compound)
        db.flush()

        cid=compound.id

        db.add_all([
            Vial(
                compound_id=cid,
                content_value=10,
                content_unit='mg',
                status='sealed'
            ),
            Vial(
                compound_id=cid,
                content_value=10,
                content_unit='mg',
                status='discarded'
            )
        ])

        db.commit()

    with Session(engine) as db:
        active=list(
            db.scalars(vial_listing('active',cid))
        )

        all_vials=list(
            db.scalars(vial_listing('all',cid))
        )

        missing=list(
            db.scalars(vial_listing('active',cid+1))
        )

        assert len(active)==1
        assert len(all_vials)==2
        assert len(missing)==0
        assert list(db.scalars(purchase_listing()))==[]

    engine.dispose()
