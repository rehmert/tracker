"""Release 807 isolated functional, compatibility, and workspace checks."""
from datetime import date, datetime, timedelta
from types import SimpleNamespace
import json
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, select, inspect
from sqlalchemy.orm import Session
from app.db import Base
from app.models import Compound, Vial, DoseLog, Blend, BlendDose, RegimenItem, RegimenEntry
from app.anatomical_sites807 import SITES, SITE_BY_CODE, site_geometry, valid_site, configured_rotation, next_rotation_site
from app.wellness807 import metric_values, metric_summary, METRICS, episode_values, REACTIONS
from app.wellness_models807 import WellnessDay807, SiteReaction807, RotationPreference807
from app.site_history807 import history807, save_context807, site_snapshot807, rotation_key807
from app.health_analytics807 import cycle_samples807, cycle_summary807, periods807, site_analytics807, weekly_report807
from app.routers.wellness807 import router
from app.scoped_db390 import get_scoped_db390
from app.progress_goals807 import milestones807, projections807

NEW_TABLES = {t.name for t in Base.metadata.tables.values() if t.name.endswith("807")}

def engine_at(path):
    engine = create_engine("sqlite:///" + str(path), connect_args={"check_same_thread": False})
    @event.listens_for(engine, "connect")
    def fk(connection, _):
        connection.execute("PRAGMA foreign_keys=ON")
    return engine

@pytest.fixture
def isolated807(tmp_path):
    engine = engine_at(tmp_path / "wellness.sqlite")
    Base.metadata.create_all(engine)
    web = FastAPI()
    web.include_router(router)
    def scoped():
        with Session(engine) as db:
            yield db
    web.dependency_overrides[get_scoped_db390] = scoped
    with TestClient(web, follow_redirects=False) as client:
        yield client, engine
    engine.dispose()

def seed(db, now):
    compound=Compound(name="Synthetic test compound")
    db.add(compound)
    db.flush()
    vial=Vial(compound_id=compound.id,content_value=50,content_unit="mg")
    blend=Blend(label="Synthetic blend",final_volume_ml=2)
    db.add_all([vial,blend]); db.flush()
    dose=DoseLog(vial_id=vial.id,taken_at=now-timedelta(days=2),entered_value=1,entered_unit="mg",amount_base=1000,site="abdomen_left")
    waste=DoseLog(vial_id=vial.id,taken_at=now-timedelta(days=1),entered_value=1,entered_unit="mg",amount_base=1000,kind="waste",site="abdomen_right")
    draw=BlendDose(blend_id=blend.id,taken_at=now-timedelta(hours=4),volume_ml=.1,site="abdomen_left")
    med=RegimenItem(name="Synthetic medication",kind="medication")
    db.add_all([dose,waste,draw,med]); db.flush()
    entry=RegimenEntry(item_id=med.id,logged_at=now-timedelta(hours=1),outcome="taken",amount="Recorded amount")
    db.add(entry); db.flush()
    save_context807(db,"dose",dose,"subcutaneous")
    save_context807(db,"blend",draw,"subcutaneous")
    save_context807(db,"regimen",entry,"intramuscular",site="deltoid_right_mid")
    db.commit()
    return dose.id, draw.id, compound.id

def test_registry_orientation_and_legacy():
    assert len(SITES)==len(SITE_BY_CODE)==24
    for site in SITES:
        geometry=site_geometry(site.code)
        assert set(geometry)==set(site.views)
        for x,y,w,h in geometry.values():
            assert 0<=x<x+w<=300 and 0<=y<y+h<=460
    assert site_geometry("abdomen_left")["front"][0]>150
    assert site_geometry("glute_left_upper_outer")["rear"][0]<150
    assert valid_site("Historic free text",previous="Historic free text")
    assert not valid_site("Historic free text")

def test_rotation_is_opt_in_and_respects_scope_and_exclusion():
    now=datetime.now()
    left,right="abdomen_left","abdomen_right"
    cfg={("global",None,"subcutaneous"):(left,right),("compound",3,"subcutaneous"):()}
    assert configured_rotation(cfg,route="subcutaneous",compound=3)==()
    assert configured_rotation(cfg,route="intramuscular")==()
    assert next_rotation_site((left,right),left,{right:now},set(),24,now)==left
    assert next_rotation_site((left,right),left,{right:now},{left},24,now) is None

def test_optional_ratings_and_missing_values():
    assert len(METRICS)==15
    assert metric_values({"hunger":"3","energy":"","sleep_duration":"6.5"},("hunger","energy","sleep_duration"))=={"hunger":3,"sleep_duration":6.5}
    with pytest.raises(ValueError):
        metric_values({"energy":"nan"},("energy",))
    summary=metric_summary([SimpleNamespace(values_json='{"energy":4}'),SimpleNamespace(values_json='{}')])
    assert summary["energy"]=={"count":1,"average":4}
    assert summary["hunger"]=={"count":0,"average":None}

def test_workspace_isolation_and_additive_schema(tmp_path):
    a=engine_at(tmp_path/"a.sqlite"); b=engine_at(tmp_path/"b.sqlite")
    old=[t for t in Base.metadata.sorted_tables if t.name not in NEW_TABLES]
    Base.metadata.create_all(a,tables=old)
    with Session(a) as db:
        db.add(Compound(name="Preserved")); db.commit()
    before=set(inspect(a).get_table_names())
    Base.metadata.create_all(a); Base.metadata.create_all(a); Base.metadata.create_all(b)
    assert set(inspect(a).get_table_names())-before==NEW_TABLES
    with Session(a) as db:
        assert db.scalar(select(Compound)).name=="Preserved"
        db.add(WellnessDay807(day=date.today(),values_json='{"energy":5}')); db.commit()
    with Session(b) as db:
        assert db.scalar(select(WellnessDay807)) is None
    a.dispose(); b.dispose()

def test_actual_physical_history_and_rotation(isolated807):
    _,engine=isolated807
    now=datetime.now().replace(microsecond=0)
    with Session(engine) as db:
        seed(db,now)
        rows,truncated=history807(db,now-timedelta(days=7),now)
        assert not truncated and len(rows)==3
        assert {r["source"] for r in rows}=={"dose","blend","regimen"}
        assert sum(r["site"]=="abdomen_left" for r in rows)==2
        assert site_snapshot807(db,now)["next_site"] is None
        db.add(RotationPreference807(key=rotation_key807("global",None,"subcutaneous"),route="subcutaneous",sequence_json=json.dumps(["abdomen_left","abdomen_right"]),minimum_hours=24)); db.commit()
        assert site_snapshot807(db,now,route="subcutaneous")["next_site"]=="abdomen_right"
        report=site_analytics807(db,now-timedelta(days=7),now)
        assert report["count"]==3 and sum(r["reported"] for r in report["stats"])==0

def test_wellness_crud_and_symptoms(isolated807):
    client,engine=isolated807
    day=date.today().isoformat()
    assert client.post("/wellness807/save",data={"day":day,"energy":"4","hunger":"2"}).status_code==303
    assert client.post("/wellness807/save",data={"day":day,"energy":"6"}).status_code==422
    with Session(engine) as db:
        row=db.scalar(select(WellnessDay807)); rid=row.id
        assert json.loads(row.values_json)=={"energy":4,"hunger":2}
    assert client.post("/wellness807/save",data={"day":day,"energy":"3"}).status_code==303
    with Session(engine) as db:
        assert json.loads(db.get(WellnessDay807,rid).values_json)=={"energy":3}
    assert client.post(f"/wellness807/days/{rid}/delete").status_code==303
    stamp=(datetime.now()-timedelta(hours=1)).isoformat(timespec="minutes")
    assert client.post("/wellness807/symptoms/save",data={"kind":"Nausea","severity":"2","onset_at":stamp}).status_code==303

def test_reaction_absence_and_parent_validation(isolated807):
    client,engine=isolated807
    now=datetime.now().replace(microsecond=0)
    with Session(engine) as db:
        did,_,_=seed(db,now)
    form={"kind":"No reaction reported","severity":"0","onset_at":(now-timedelta(hours=1)).isoformat(timespec="minutes")}
    assert client.post(f"/wellness807/reactions/dose/{did}/save",data=form).status_code==303
    assert client.post(f"/wellness807/reactions/dose/{did}/save",data={**form,"kind":"Redness","severity":"2"}).status_code==422
    assert client.post("/wellness807/reactions/dose/987654/save",data=form).status_code==404
    with Session(engine) as db:
        row=db.scalar(select(SiteReaction807)); rid=row.id
        report=site_analytics807(db,now-timedelta(days=7),now)
        assert sum(r["reported"] for r in report["stats"])==1
        assert sum(r["reactions"] for r in report["stats"])==0
    assert client.post(f"/wellness807/reactions/dose/{did}/{rid}/delete").status_code==303

def test_actual_cycle_and_periods():
    now=datetime.now()
    actual=[(now-timedelta(days=3),2.5),(now,3)]
    observed=[(now-timedelta(days=4),5),(now-timedelta(days=1),4),(now,2)]
    samples=cycle_samples807(observed,actual)
    assert [r[2] for r in samples]==[48,0]
    assert sum(r["count"] for r in cycle_summary807(samples))==2
    assert len(periods807(actual))==2

def test_goal_projection_no_data_and_flat_trend():
    today=date.today()
    points=[(today-timedelta(days=i),100) for i in range(30, -1, -1)]
    projected=projections807(points,today,80)
    assert all(p.get("date") is None for p in projected) or all(not p.get("projected") for p in projected)
