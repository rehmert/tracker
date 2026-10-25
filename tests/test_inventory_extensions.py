from fastapi.testclient import TestClient
from app.main import app
from app.db import SessionLocal
from app.models import Compound, Purchase, Vial, Supply, Coa, DoseLog
from datetime import date


def test_new_inventory_and_coa_flow():
    with TestClient(app, follow_redirects=False) as client:
        with SessionLocal() as db:
            c = Compound(name='Extension Test', category='peptide')
            p = Purchase(vendor='Test', purchased_on=date.today())
            db.add_all([c,p]);db.commit()
            cid,pid=c.id,p.id
        r=client.post(f'/purchases/{pid}/vials', data={'compound_id':cid,'kit_size':5,'kit_count':2,'content_value':'10','content_unit':'mg','cap_color':'blue'})
        assert r.status_code == 303
        with SessionLocal() as db:
            vs=db.query(Vial).filter(Vial.purchase_id==pid).order_by(Vial.id).all()
            assert len(vs)==10 and all(v.cap_color=='blue' for v in vs)
            assert vs[0].kit_ref != vs[5].kit_ref
            ids=[v.id for v in vs]
        r=client.post(f'/vials/{ids[0]}/coas',data={'lab_name':'Lab Test','purity_pct':'99.5','endotoxin_pct':'0.1','job_id':'J1','verify_code':'V1','reported_content':'10.3','reported_unit':'mg'})
        assert r.status_code == 303
        with SessionLocal() as db:
            coa=db.query(Coa).order_by(Coa.id.desc()).first()
            coa_id=coa.id
            assert coa.original_name=='' and coa.job_id=='J1'
        assert client.post(f'/coas/{coa_id}/assign',data={'vial_ids':[str(i) for i in ids]}).status_code==303
        with SessionLocal() as db:
            assert len(db.get(Coa,coa_id).vials)==10
        assert 'Lab Test' in client.get(f'/vials/{ids[1]}').text
        assert client.post('/supplies',data={'purchase_id':pid,'name':'BAC 30 mL','kind':'bac_water','quantity':'30'}).status_code==303
        with SessionLocal() as db:
            sid=db.query(Supply).order_by(Supply.id.desc()).first().id
        assert client.post(f'/vials/{ids[0]}/reconstitute',data={'volume_ml':'2','supply_id':str(sid)}).status_code==303
        with SessionLocal() as db:
            assert db.get(Supply,sid).remaining_qty==28
        assert client.post('/doses',data={'vial_id':ids[0],'amount':'0','unit':'mg','use_remaining':'yes'}).status_code==200
        with SessionLocal() as db:
            dose=db.query(DoseLog).filter(DoseLog.vial_id==ids[0]).order_by(DoseLog.id.desc()).first()
            did=dose.id
            assert dose.amount_base==10000
        assert client.post(f'/doses/{did}/edit',data={'amount':'5','unit':'mg','site':'Abdomen lower left'}).status_code==303
        with SessionLocal() as db:
            assert db.get(DoseLog,did).amount_base==5000
