from app.routers.exports import DATASETS, csv_text

def test_export_datasets():
    assert {'vitals','doses','vials','supplies','purchases','compounds'} <= set(DATASETS)

def test_csv_headers():
    from app.db import SessionLocal, Base, engine
    Base.metadata.create_all(engine)
    db=SessionLocal()
    try: assert csv_text(db,'vitals').startswith('id,measured_at,weight_kg')
    finally: db.close()

def test_csv_formula_injection():
    from app.db import SessionLocal, Base, engine
    Base.metadata.create_all(engine)
    db=SessionLocal()
    from app.models import Compound
    try:
        db.add(Compound(name='=HYPERLINK("evil")',category='other',notes=''))
        db.commit()
        assert "'=HYPERLINK" in csv_text(db,'compounds')
    finally: db.rollback(); db.close()
