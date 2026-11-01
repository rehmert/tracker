"""Local, read-only search across Tracker records with enhanced functionality. No third-party services."""
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
    
    # Escape special characters for LIKE queries
    like = '%' + term.replace('!', '!!').replace('%', '!%').replace('_', '!_') + '%'
    
    results = []
    def add(kind, label, url, detail='', relevance=0):
        if len(results) < 36:
            results.append({
                'type': kind, 
                'label': label, 
                'url': url, 
                'detail': detail,
                'relevance': relevance
            })
    
    # Search compounds with relevance scoring
    compound_results = []
    for c in db.scalars(select(Compound).where(Compound.name.ilike(like, escape='!')).order_by(Compound.name).limit(8)):
        relevance = 100 if c.name.lower() == term.lower() else 50
        compound_results.append((c, relevance))
    
    compound_results.sort(key=lambda x: x[1], reverse=True)
    for c, relevance in compound_results:
        add('Compound', c.name, '/compounds', c.category, relevance)
    
    # Search vials with relevance scoring
    vial_results = []
    for v in db.scalars(select(Vial).join(Compound).where(or_(
        Vial.label.ilike(like, escape='!'), 
        Vial.lot.ilike(like, escape='!'), 
        Compound.name.ilike(like, escape='!')
    )).order_by(Vial.id.desc()).limit(10)):
        relevance = 0
        if v.label and term.lower() in v.label.lower():
            relevance = 80
        elif v.lot and term.lower() in v.lot.lower():
            relevance = 70
        elif v.compound.name.lower() == term.lower():
            relevance = 90
        else:
            relevance = 40
        vial_results.append((v, relevance))
    
    vial_results.sort(key=lambda x: x[1], reverse=True)
    for v, relevance in vial_results:
        add('Vial', v.compound.name + ' · ' + (v.label or '#' + str(v.id)), '/vials/' + str(v.id), v.status, relevance)
    
    # Search protocols with relevance scoring
    protocol_results = []
    for r in db.scalars(select(Protocol).where(Protocol.name.ilike(like, escape='!')).order_by(Protocol.name).limit(8)):
        relevance = 100 if r.name.lower() == term.lower() else 50
        protocol_results.append((r, relevance))
    
    protocol_results.sort(key=lambda x: x[1], reverse=True)
    for r, relevance in protocol_results:
        add('Protocol', r.name, '/protocols/' + str(r.id), 'Active' if r.is_active else 'What-if', relevance)
    
    # Search purchases with relevance scoring
    purchase_results = []
    for x in db.scalars(select(Purchase).where(or_(
        Purchase.vendor.ilike(like, escape='!'), 
        Purchase.order_ref.ilike(like, escape='!'), 
        Purchase.notes.ilike(like, escape='!')
    )).order_by(Purchase.id.desc()).limit(6)):
        relevance = 0
        if x.vendor.lower() == term.lower():
            relevance = 90
        elif x.vendor and term.lower() in x.vendor.lower():
            relevance = 70
        elif x.order_ref and term.lower() in x.order_ref.lower():
            relevance = 60
        else:
            relevance = 30
        purchase_results.append((x, relevance))
    
    purchase_results.sort(key=lambda x: x[1], reverse=True)
    for x, relevance in purchase_results:
        add('Purchase', x.vendor + ' · #' + str(x.id), '/purchases/' + str(x.id), str(x.purchased_on), relevance)
    
    # Search supplies with relevance scoring
    supply_results = []
    for s in db.scalars(select(Supply).where(or_(
        Supply.name.ilike(like, escape='!'), 
        Supply.kind.ilike(like, escape='!'), 
        Supply.notes.ilike(like, escape='!')
    )).order_by(Supply.id.desc()).limit(8)):
        relevance = 0
        if s.name.lower() == term.lower():
            relevance = 90
        elif s.name and term.lower() in s.name.lower():
            relevance = 70
        else:
            relevance = 30
        supply_results.append((s, relevance))
    
    supply_results.sort(key=lambda x: x[1], reverse=True)
    for s, relevance in supply_results:
        add('Supply', s.name + ' · #' + str(s.id), '/supplies', s.kind, relevance)
    
    # Search lab reports with relevance scoring
    lab_results = []
    for r in db.scalars(select(LabReport).where(or_(
        LabReport.lab_name.ilike(like, escape='!'), 
        LabReport.notes.ilike(like, escape='!')
    )).order_by(LabReport.drawn_on.desc()).limit(6)):
        relevance = 0
        if r.lab_name and term.lower() == r.lab_name.lower():
            relevance = 80
        elif r.lab_name and term.lower() in r.lab_name.lower():
            relevance = 60
        else:
            relevance = 30
        lab_results.append((r, relevance))
    
    lab_results.sort(key=lambda x: x[1], reverse=True)
    for r, relevance in lab_results:
        add('Lab Report', r.lab_name or 'Lab Report', '/labs/' + str(r.id), r.notes[:100] if r.notes else '', relevance)
    
    # Sort all results by relevance score
    results.sort(key=lambda x: x['relevance'], reverse=True)
    
    return {'results': results, 'query': term}