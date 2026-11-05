from datetime import date

from sqlalchemy import create_engine,event
from sqlalchemy.orm import Session

from app.db import Base
from app.models import Compound,Purchase
from app.list_queries297 import purchase_listing
from app.routers.exports import csv_lines,csv_text


def test_csv_streaming_preserves_content_and_formula_escape(
    tmp_path
):
    engine=create_engine(
        f'sqlite:///{tmp_path / "csv.db"}'
    )
    Base.metadata.create_all(engine)

    with Session(engine) as db:
        db.add_all([
            Compound(name='=FORMULA',category='peptide'),
            Compound(name='Control',category='peptide')
        ])
        db.commit()

    with Session(engine) as db:
        chunks=list(csv_lines(db,'compounds'))

        assert len(chunks)==3
        assert ''.join(chunks)==csv_text(db,'compounds')
        assert "'=FORMULA" in ''.join(chunks)

    engine.dispose()


def test_purchase_listing_query_count_is_bounded(tmp_path):
    engine=create_engine(
        f'sqlite:///{tmp_path / "queries.db"}'
    )
    Base.metadata.create_all(engine)

    with Session(engine) as db:
        for n in range(10):
            purchase=Purchase(
                vendor=f'Vendor-{n}',
                purchased_on=date(2026,11,4)
            )
            db.add(purchase)
            db.flush()

        db.commit()

    counts=[]

    def collect(
        conn,cursor,statement,params,context,executemany
    ):
        if statement.strip().lower().startswith('select'):
            counts.append(statement)

    event.listen(
        engine,'before_cursor_execute',collect
    )

    try:
        with Session(engine) as db:
            items=list(db.scalars(purchase_listing()))

            assert len(items)==10

            for item in items:
                assert list(item.vials)==[]
                assert list(item.supplies)==[]

        assert len(counts)<=3,len(counts)
    finally:
        event.remove(
            engine,'before_cursor_execute',collect
        )
        engine.dispose()
