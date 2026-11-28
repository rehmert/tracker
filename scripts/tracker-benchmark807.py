"""Representative synthetic history benchmark, independent of installed data."""
import statistics
import time
from datetime import datetime,timedelta
from sqlalchemy import create_engine, select, event
from sqlalchemy.orm import Session
from app.db import Base
from app.models import Compound,Vial,DoseLog
from app.site_history807 import history807,site_snapshot807
from app.health_analytics807 import site_analytics807

engine=create_engine("sqlite://")
Base.metadata.create_all(engine)
now=datetime.now().replace(microsecond=0)
with Session(engine) as db:
    c=Compound(name="Synthetic benchmark compound")
    db.add(c); db.flush()
    v=Vial(compound_id=c.id,content_value=100000,content_unit="mg")
    db.add(v); db.flush()
    db.add_all(DoseLog(vial_id=v.id,taken_at=now-timedelta(hours=i*3),entered_value=1,entered_unit="mg",amount_base=1000,site="abdomen_left" if i%2 else "abdomen_right",kind="waste" if i%11==0 else "dose") for i in range(12000))
    db.commit()
    start=now-timedelta(days=90)
    statements=[]
    @event.listens_for(engine,"before_cursor_execute")
    def count(*args):
        statements.append(1)
    def bench(name,call):
        durations=[];counts=[]
        for _ in range(7):
            statements.clear()
            t=time.perf_counter(); call()
            durations.append((time.perf_counter()-t)*1000);counts.append(len(statements))
        print(f"RELEASE_807_BENCHMARK_{name} median_ms={statistics.median(durations):.2f} queries={max(counts)} synthetic_rows=12000")
        return max(counts)
    assert bench("LEGACY_ACTUAL_HISTORY",lambda:db.execute(select(DoseLog.id,DoseLog.taken_at,DoseLog.site).where(DoseLog.kind=="dose",DoseLog.taken_at>=start,DoseLog.taken_at<=now).order_by(DoseLog.taken_at.desc()).limit(5000)).all())==1
    assert bench("UNIFIED_HISTORY",lambda:history807(db,start,now,limit=5000))==1
    assert bench("SITE_ANALYTICS",lambda:site_analytics807(db,start,now))<=5
    assert bench("ROTATION_SNAPSHOT",lambda:site_snapshot807(db,now))<=8
engine.dispose()
