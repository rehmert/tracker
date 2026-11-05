from datetime import date
from sqlalchemy import create_engine,event
from sqlalchemy.orm import Session

from app.db import Base
from app.models import (
    Compound,Purchase,Vial,Supply,SupplyUsage,
    PreparationEvent,PreparationSupply
)
from app.preparation_reads345 import load_preparations
from app.services import vial_views


def test_preparation_queries_remain_bounded(tmp_path):
    engine=create_engine(
        f'sqlite:///{tmp_path / "vial.db"}'
    )
    Base.metadata.create_all(engine)

    with Session(engine) as db:
        c=Compound(name='Perf')
        p=Purchase(
            vendor='Perf',
            purchased_on=date(2026,11,4)
        )
        db.add_all([c,p])
        db.flush()

        v=Vial(
            compound_id=c.id,
            purchase_id=p.id,
            status='sealed',
            content_value=10,
            content_unit='mg'
        )
        u=Supply(
            purchase_id=p.id,
            name='syringe',
            kind='needle',
            purchased_qty=100,
            remaining_qty=80
        )
        db.add_all([v,u])
        db.flush()

        for i in range(25):
            ev=PreparationEvent(
                vial_id=v.id,
                kind='filtering'
            )
            usage=SupplyUsage(
                supply_id=u.id,
                vial_id=v.id,
                amount=1
            )
            db.add_all([ev,usage])
            db.flush()

            db.add(
                PreparationSupply(
                    event_id=ev.id,
                    usage_id=usage.id
                )
            )

        db.commit()
        vid=v.id

    queries=[]

    def collect(conn,cursor,sql,params,context,many):
        if sql.lstrip().lower().startswith('select'):
            queries.append(sql)

    event.listen(
        engine,'before_cursor_execute',collect
    )

    try:
        with Session(engine) as db:
            events,usage=load_preparations(db,vid)

            assert len(events)==25
            assert all(len(usage[e.id])==1 for e in events)
            assert all(
                usage[e.id][0][1].name=='syringe'
                for e in events
            )
            assert len(queries)<=4,queries

            queries.clear()
            view=vial_views(db,[db.get(Vial,vid)])[vid]
            assert view.id==vid

            totals=[
                query.lower()
                for query in queries
                if 'sum(' in query.lower()
            ]
            assert len(totals)==2
            assert all(' in (' in query for query in totals)
    finally:
        event.remove(
            engine,'before_cursor_execute',collect
        )
        engine.dispose()
