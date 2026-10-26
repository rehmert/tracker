from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.staticfiles import StaticFiles

from . import config, models  # noqa: F401  (models import registers tables)
from .db import Base, engine
from .routers import (coas, compounds, dashboard, doses, labs, pages, protocols, purchases, supplies,
                      vials, vitals, pk, calendar, backups, search, inventory_intelligence, health_timeline, health_insights, exports, reliability)
from .security import require_auth


@asynccontextmanager
async def lifespan(_app: FastAPI):
    from .migrations import migrate
    migrate(engine)
    Base.metadata.create_all(engine)
    # A stable schema marker for future migration tooling and support checks.
    with engine.begin() as conn:
        conn.exec_driver_sql("""CREATE TABLE IF NOT EXISTS tracker_schema_migrations
            (name TEXT PRIMARY KEY, applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)""")
        conn.exec_driver_sql("INSERT OR IGNORE INTO tracker_schema_migrations(name) VALUES ('tracker_phases_1_3_v2')")
    yield


app = FastAPI(title="Tracker", dependencies=[Depends(require_auth)],
              lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)
app.mount("/static", StaticFiles(directory=config.BASE_DIR / "static"), name="static")

for module in (dashboard, compounds, purchases, vials, coas, doses, supplies, vitals, labs, protocols, pages, pk, calendar, backups, search, inventory_intelligence, health_timeline, health_insights, exports, reliability):
    app.include_router(module.router)


@app.get("/ping")
def ping():
    return{"status": "alive"}

@app.get("/healthz", include_in_schema=False)
def healthz():
    return {"ok": True}
