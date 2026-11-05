from datetime import date

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session

from app.db import Base
from app.models import (
    Compound, Purchase, Supply, Vial, SupplyUsage
)
from app.inventory_consistency import inspect_inventory


def test_inventory_findings_use_bounded_selects(tmp_path):
    engine = create_engine(
        f'sqlite:///{tmp_path / "inventory.db"}'
    )
    Base.metadata.create_all(engine)

    with Session(engine) as db:
        c = Compound(name='Batch-318-test')
        p = Purchase(
            vendor='Test',
            purchased_on=date(2026, 11, 4)
        )
        db.add_all([c, p])
        db.flush()

        for i in range(30):
            supply = Supply(
                purchase_id=p.id,
                name=f'supply-{i}',
                kind='needle',
                purchased_qty=10,
                remaining_qty=10
            )
            vial = Vial(
                compound_id=c.id,
                purchase_id=p.id,
                status='sealed',
                content_value=10,
                content_unit='mg'
            )
            db.add_all([supply, vial])
            db.flush()

            if i == 2:
                supply.remaining_qty = 7
                db.add(
                    SupplyUsage(
                        supply_id=supply.id,
                        amount=1
                    )
                )

        db.commit()

    counts = []

    def count(
        _conn, _cursor, statement,
        _params, _context, _many
    ):
        if statement.lstrip().lower().startswith('select'):
            counts.append(statement)

    event.listen(
        engine,
        'before_cursor_execute',
        count
    )

    try:
        with Session(engine) as db:
            findings = inspect_inventory(db)

            assert len(counts) <= 6, counts

            mismatches = [
                finding for finding in findings
                if finding.code == 'ledger_mismatch'
            ]
            assert len(mismatches) == 1
            assert mismatches[0].expected == 9
            assert mismatches[0].observed == 7

            assert not db.new
            assert not db.dirty
            assert not db.deleted
    finally:
        event.remove(
            engine,
            'before_cursor_execute',
            count
        )
        engine.dispose()
