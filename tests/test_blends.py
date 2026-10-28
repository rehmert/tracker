from fastapi.testclient import TestClient
from app.main import app
from app.db import SessionLocal
from app.models import Compound, Vial, Blend, BlendDose
from app.services import vial_views


def test_blend_transfer_and_draw_and_reject_mismatched_targets():
    with TestClient(app) as client:
        with SessionLocal() as db:
            a = Compound(name='Blend A', primary_unit='mg')
            b = Compound(name='Blend B', primary_unit='mg')
            db.add_all([a, b]); db.flush()
            va = Vial(compound_id=a.id, content_value=10, content_unit='mg', status='sealed', volume_ml=1)
            vb = Vial(compound_id=b.id, content_value=20, content_unit='mg', status='sealed', volume_ml=1)
            db.add_all([va, vb]); db.commit()
            ids = [va.id, vb.id]
        data = {'label':'Blend demo', 'diluent_ml':'0', 'capacity_ml':'3',
                'source_id':[str(i) for i in ids], 'transfer_amount':['10','20'],
                'transfer_unit':['mg','mg'], 'target_amount':['1','2'],
                'target_unit':['mg','mg']}
        resp=client.post('/blends',data=data,follow_redirects=False)
        assert resp.status_code == 303
        assert '/blends/' in resp.headers['location']
        with SessionLocal() as db:
            blend = db.query(Blend).filter_by(label='Blend demo').one()
            assert len(blend.components)==2
            assert blend.final_volume_ml == 2
            assert all(vial_views(db,[db.get(Vial,i)])[i].remaining_base == 0 for i in ids)
            blend_id=blend.id
        resp=client.post(f'/blends/{blend_id}/doses',data={'volume_ml':'0.2','taken_at':'2026-10-27T12:00','kind':'dose'},follow_redirects=False)
        assert resp.status_code == 303
        with SessionLocal() as db:
            blend=db.get(Blend,blend_id)
            assert len(blend.doses)==1
            assert abs(sum(d.volume_ml for d in blend.doses)-0.2)<1e-8
        bad=dict(data,label='Invalid blend',target_amount=['1','5'])
        resp=client.post('/blends',data=bad,follow_redirects=False)
        assert 'err=' in resp.headers['location']
        with SessionLocal() as db:
            assert db.query(Blend).filter_by(label='Invalid blend').count()==0


def test_blend_preview_does_not_change_inventory():
    with TestClient(app) as client:
        with SessionLocal() as db:
            a = Compound(name='Preview A', primary_unit='mg')
            b = Compound(name='Preview B', primary_unit='mg')
            db.add_all([a,b]); db.flush()
            va = Vial(compound_id=a.id, content_value=10, content_unit='mg', status='sealed', volume_ml=1)
            vb = Vial(compound_id=b.id, content_value=20, content_unit='mg', status='sealed', volume_ml=1)
            db.add_all([va,vb]); db.commit()
            ids=[va.id,vb.id]
            initial_blends=db.query(Blend).count()
        data={'label':'Preview only', 'diluent_ml':'0', 'capacity_ml':'3',
              'source_id':[str(i) for i in ids], 'transfer_amount':['10','20'],
              'transfer_unit':['mg','mg'], 'target_amount':['1','2'],
              'target_unit':['mg','mg']}
        response=client.post('/blends/preview',data=data)
        assert response.status_code==200
        assert '0.2 mL' in response.text
        assert '10 U-100 units' not in response.text
        assert '20 U-100 units' in response.text
        with SessionLocal() as db:
            assert db.query(Blend).count()==initial_blends
            assert all(db.get(Vial,i).status=='sealed' for i in ids)
            assert [vial_views(db,[db.get(Vial,i)])[i].remaining_base for i in ids]==[10000,20000]
        bad=dict(data,target_amount=['1','5'])
        response=client.post('/blends/preview',data=bad)
        assert response.status_code==422
        assert 'different draw volumes' in response.text


def test_reconstitution_preview_is_read_only_and_checks_capacity():
    with TestClient(app) as client:
        with SessionLocal() as db:
            a=Compound(name='Recon Test A', primary_unit='mg')
            b=Compound(name='Recon Test B', primary_unit='mg')
            db.add_all([a,b]); db.flush()
            va=Vial(compound_id=a.id,content_value=10,content_unit='mg',status='sealed')
            vb=Vial(compound_id=b.id,content_value=20,content_unit='mg',status='sealed')
            db.add_all([va,vb]); db.commit(); ids=[va.id,vb.id]; before=db.query(Blend).count()
        data={'source_id':[str(i) for i in ids], 'target_amount':['1','2'],
              'target_unit':['mg','mg'], 'source_bac_ml':['0.5','0.5'],
              'planner_draw_ml':'0.2','planner_capacity_ml':'3','planner_allocation':'equal'}
        response=client.post('/blends/reconstitution-preview',data=data)
        assert response.status_code==200
        assert '10 complete draws' in response.text
        with SessionLocal() as db:
            assert db.query(Blend).count()==before
            assert all(db.get(Vial,i).volume_ml is None for i in ids)
        response=client.post('/blends/reconstitution-preview',data=dict(data,planner_capacity_ml='1.5'))
        assert response.status_code==200
        assert '7 complete draws' in response.text
        response=client.post('/blends/reconstitution-preview',data=dict(data,target_amount=['11','2']))
        assert response.status_code==422
        assert 'Not enough source content' in response.text


def test_reconstitution_preview_manual_source_bac():
    with TestClient(app) as client:
        with SessionLocal() as db:
            a=Compound(name='Manual Recon A',primary_unit='mg')
            b=Compound(name='Manual Recon B',primary_unit='mg')
            db.add_all([a,b]);db.flush()
            va=Vial(compound_id=a.id,content_value=10,content_unit='mg',status='sealed')
            vb=Vial(compound_id=b.id,content_value=20,content_unit='mg',status='sealed')
            db.add_all([va,vb]);db.commit();ids=[va.id,vb.id]
        data={'source_id':[str(i) for i in ids], 'target_amount':['1','2'],
              'target_unit':['mg','mg'], 'source_bac_ml':['0.5','1'],
              'planner_draw_ml':'0.2', 'planner_capacity_ml':'3','planner_allocation':'manual'}
        r=client.post('/blends/reconstitution-preview',data=data)
        assert r.status_code==200, r.text
        assert '10 complete draws' in r.text
        assert 'Additional BAC in destination vial: <strong>0.5 mL</strong>' in r.text
        with SessionLocal() as db:
            assert all(db.get(Vial,i).volume_ml is None for i in ids)


def test_auto_reconstitution_calculates_source_bac_and_draws():
    with TestClient(app) as client:
        with SessionLocal() as db:
            a=Compound(name='Auto BAC A',primary_unit='mg')
            b=Compound(name='Auto BAC B',primary_unit='mg')
            db.add_all([a,b]);db.flush()
            va=Vial(compound_id=a.id,content_value=10,content_unit='mg',status='sealed')
            vb=Vial(compound_id=b.id,content_value=20,content_unit='mg',status='sealed')
            db.add_all([va,vb]);db.commit();ids=[va.id,vb.id]
        data={'source_id':[str(i) for i in ids], 'target_amount':['1','2'],
              'target_unit':['mg','mg'], 'source_bac_ml':['0.5','0.5'],
              'planner_draw_ml':'0.2','planner_capacity_ml':'3','planner_allocation':'equal'}
        r=client.post('/blends/reconstitution-preview',data=data)
        assert r.status_code==200, r.text
        assert 'Target final volume: <strong>2 mL</strong>' in r.text
        assert '<td>10 mg</td><td>1</td><td>0</td>' in r.text and '<td>20 mg</td><td>1</td><td>0</td>' in r.text
        assert 'Additional BAC in destination vial: <strong>0 mL</strong>' in r.text


def test_max_draw_planner_derives_transfer_amounts_without_user_transfer_fields():
    with TestClient(app) as client:
        with SessionLocal() as db:
            a = Compound(name='MaxDraw A', primary_unit='mg')
            b = Compound(name='MaxDraw B', primary_unit='mg')
            db.add_all([a,b]); db.flush()
            va = Vial(compound_id=a.id, content_value=10, content_unit='mg', status='sealed')
            vb = Vial(compound_id=b.id, content_value=20, content_unit='mg', status='sealed')
            db.add_all([va,vb]); db.commit(); ids=[va.id,vb.id]
            before=db.query(Blend).count()
        data={'source_id':[str(i) for i in ids], 'target_amount':['1','2'],
              'target_unit':['mg','mg'], 'source_bac_ml':['0.5','0.5'],
              'planner_draw_ml':'0.2', 'planner_capacity_ml':'3', 'planner_allocation':'equal'}
        r=client.post('/blends/reconstitution-preview',data=data)
        assert r.status_code==200, r.text
        assert '10 complete draws' in r.text
        assert 'Target final volume: <strong>2 mL</strong>' in r.text
        assert '10 mg' in r.text and '20 mg' in r.text
        with SessionLocal() as db:
            assert db.query(Blend).count()==before
            assert all(db.get(Vial,i).volume_ml is None for i in ids)
        r=client.post('/blends/reconstitution-preview',data=dict(data,planner_capacity_ml='1.5'))
        assert r.status_code==200
        assert '7 complete draws' in r.text
        assert 'Target final volume: <strong>1.4 mL</strong>' in r.text


def test_multiple_destinations_preview_and_recording():
    with TestClient(app) as client:
        with SessionLocal() as db:
            a=Compound(name='MultiDest A',primary_unit='mg')
            b=Compound(name='MultiDest B',primary_unit='mg')
            db.add_all([a,b]);db.flush()
            va=Vial(compound_id=a.id,content_value=10,content_unit='mg',status='sealed',volume_ml=1)
            vb=Vial(compound_id=b.id,content_value=20,content_unit='mg',status='sealed',volume_ml=1)
            db.add_all([va,vb]);db.commit();ids=[va.id,vb.id]
        planner={'source_id':list(map(str,ids)), 'target_amount':['1','2'],
                 'target_unit':['mg','mg'], 'source_bac_ml':['0','0'],
                 'planner_draw_ml':'0.2','planner_capacity_ml':'1.5',
                 'planner_max_destinations':'2','planner_allocation':'equal'}
        r=client.post('/blends/reconstitution-preview',data=planner)
        assert r.status_code==200,r.text
        assert '10 complete draws across 2 destination vials' in r.text
        assert 'Vial 1: 1.4 mL (7 draws)' in r.text
        assert 'Vial 2: 0.6 mL (3 draws)' in r.text
        form={'label':'Multi destination record','destination_count':'2','diluent_ml':'0',
              'capacity_ml':'1.5','source_id':list(map(str,ids)),
              'transfer_amount':['10','20'],'transfer_unit':['mg','mg'],
              'target_amount':['1','2'],'target_unit':['mg','mg']}
        r=client.post('/blends/preview',data=form)
        assert r.status_code==200,r.text
        assert 'Destination vials: <strong>2</strong>' in r.text
        r=client.post('/blends',data=form,follow_redirects=False)
        assert r.status_code==303,r.text
        with SessionLocal() as db:
            rows=db.query(Blend).filter(Blend.label.like('Multi destination record%')).all()
            assert len(rows)==2
            assert all(abs(b.final_volume_ml-1)<1e-8 for b in rows)
            assert all(len(b.components)==2 for b in rows)
            assert all(abs(b.components[0].transferred_base-5000)<1e-8 for b in rows)
            assert all(vial_views(db,[db.get(Vial,i)])[i].remaining_base==0 for i in ids)
