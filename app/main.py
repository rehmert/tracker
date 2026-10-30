"""Tracker ASGI application entry point.

Use America/New_York for naive local calendar and clock operations throughout
Tracker. Existing user-entered SQLite datetimes remain unchanged; explicit UTC
audit/backup timestamps continue to use UTC.
"""
import os
import time

# Must run before importing routers or services that compute local timestamps.
os.environ["TZ"] = "America/New_York"
if hasattr(time, "tzset"):
    time.tzset()

from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.staticfiles import StaticFiles

from . import config, models  # noqa: F401  (models import registers tables)
from .db import Base, engine
from .routers import (coas, compounds, dashboard, doses, labs, pages, protocols, purchases, supplies,
                      vials, vitals, pk, calendar, backups, search, inventory_intelligence, health_timeline, health_insights, exports, reliability, blends, vendor_prices)
from .security import require_auth
from .routers import inventory_timeline


@asynccontextmanager
async def lifespan(_app: FastAPI):
    from .migrations import migrate
    migrate(engine)
    Base.metadata.create_all(engine)
    from .migrations import migrate_coa_links
    migrate_coa_links(engine)
    # A stable schema marker for future migration tooling and support checks.
    with engine.begin() as conn:
        conn.exec_driver_sql("""CREATE TABLE IF NOT EXISTS tracker_schema_migrations
            (name TEXT PRIMARY KEY, applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)""")
        conn.exec_driver_sql("INSERT OR IGNORE INTO tracker_schema_migrations(name) VALUES ('tracker_phases_1_3_v2')")
    yield


app = FastAPI(title="Tracker", dependencies=[Depends(require_auth)],
              lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)
app.mount("/static", StaticFiles(directory=config.BASE_DIR / "static"), name="static")

for module in (dashboard, compounds, purchases, vials, coas, doses, supplies, vitals, labs, protocols, pages, pk, calendar, backups, search, inventory_intelligence, health_timeline, health_insights, exports, reliability, blends, vendor_prices):
    app.include_router(module.router)

app.include_router(inventory_timeline.router)

from .routers import consolidated_reports
app.include_router(consolidated_reports.router)

from .routers import sqlite_viewer
app.include_router(sqlite_viewer.router)


@app.get("/ping")
def ping():
    return{"status": "alive"}

@app.get("/healthz", include_in_schema=False)
def healthz():
    return {"ok": True}


# Release 65–68: Unified daily activity
from .routers import activity
app.include_router(activity.router)

# Release 69-72: read-only workflow tools
from .routers import workflow_tools
app.include_router(workflow_tools.router)

# Release 73-76: read-only record explorer
from .routers import record_explorer
app.include_router(record_explorer.router)

# Release 77-80 maintenance review
from .routers import maintenance_review
app.include_router(maintenance_review.router)
