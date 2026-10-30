"""Local, read-only search across Tracker records. No third-party services."""
from fastapi import APIRouter, Depends
from sqlalchemy import select, or_
from sqlalchemy.orm import Session
from ..db import get_db
from ..models import Compound, Vial, Protocol, Purchase, LabReport, Supply

router = APIRouter()

@router.get('/search', include_in_schema=False)
def search(q: str = '', db: Session = Depends(get_db)):
    term = q.strip()[:100]
    if len(term) < 2:
        return {'results': []}
    like = '%' + term.replace('!', '!!').replace('%', '!%').replace('_', '!_') + '%'
    results = []
    def add(kind, label, url, detail=''):
        if len(results) < 36:
            results.append({'type': kind, 'label': label, 'url': url, 'detail': detail})
    for c in db.scalars(select(Compound).where(Compound.name.ilike(like, escape='!')).order_by(Compound.name).limit(8)):
        add('Compound', c.name, '/compounds', c.category)
    for v in db.scalars(select(Vial).join(Compound).where(or_(Vial.label.ilike(like, escape='!'), Vial.lot.ilike(like, escape='!'), Compound.name.ilike(like, escape='!'))).order_by(Vial.id.desc()).limit(10)):
        add('Vial', v.compound.name + ' · ' + (v.label or '#' + str(v.id)), '/vials/' + str(v.id), v.status)
    for r in db.scalars(select(Protocol).where(Protocol.name.ilike(like, escape='!')).order_by(Protocol.name).limit(8)):
        add('Protocol', r.name, '/protocols/' + str(r.id), 'Active' if r.is_active else 'What-if')
    for x in db.scalars(select(Purchase).where(or_(Purchase.vendor.ilike(like, escape='!'), Purchase.order_ref.ilike(like, escape='!'), Purchase.notes.ilike(like, escape='!'))).order_by(Purchase.id.desc()).limit(6)):
        add('Purchase', x.vendor + ' · #' + str(x.id), '/purchases/' + str(x.id), str(x.purchased_on))
    for s in db.scalars(select(Supply).where(or_(Supply.name.ilike(like, escape='!'), Supply.kind.ilike(like, escape='!'), Supply.notes.ilike(like, escape='!'))).order_by(Supply.id.desc()).limit(8)):
        add('Supply', s.name + ' · #' + str(s.id), '/supplies', s.kind)
    for r in db.scalars(select(LabReport).where(or_(LabReport.lab_name.ilike(like, escape='!'), LabReport.notes.ilike(like, escape='!'))).order_by(LabReport.drawn_on.desc()).limit(6)):
        add('Lab report', r.lab_name or 'Lab report #' + str(r.id), '/labs/' + str(r.id), str(r.drawn_on))
    return {'results': results, 'query': term, 'total': len(results)}
