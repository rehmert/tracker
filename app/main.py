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
from fastapi.responses import PlainTextResponse

from .request_origin import reject_cross_origin_write
from .login_origin3852 import reject_write_with_login_exception
from .csrf_runtime import prepare_html_cookie
from .csrf_reporting import report_status, REPORT_HEADER
from .csrf_policy289 import reject_write

from . import config, models  # noqa: F401  (models import registers tables)
from .db import Base, engine
from .routers import (coas, compounds, dashboard, doses, labs, pages, protocols, purchases, supplies,
                      vials, vitals, pk, calendar, backups, search, inventory_intelligence, health_timeline, health_insights, exports, reliability, blends, vendor_prices)
from .security import require_auth
from . import session_auth385
from .routers import food
from .routers import food_quick375
from .routers import food_bundle376
from .routers import food_manage377
from .routers import food_review378
from .routers import food_week379
from .routers import food_search380
from .routers import session_login385
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


@app.middleware("http")
async def tracker_response_protection(request, call_next):
    """Set browser protections and reject foreign browser writes."""
    if (os.environ.get("TRACKER_ORIGIN_GUARD", "1") != "0"
            and reject_write_with_login_exception(
                request.method,
                request.url.path,
                request.headers,
            )):
        response = PlainTextResponse(
            "Cross-origin write request denied.",
            status_code=403,
        )
        csrf_report = None
    else:
        # Bounded URL-encoded inspection uses the cached
        # request body; multipart and streaming bodies are
        # left untouched for the original endpoint.
        csrf_report = await report_status(request)
        if (
            not (
                request.url.path == "/login"
                and session_auth385.enabled()
            )
            and reject_write(
                request.method,
                csrf_report,
                os.environ.get("TRACKER_CSRF_ENFORCE", "0"),
            )
        ):
            response = PlainTextResponse(
                "CSRF token required.", status_code=403
            )
        else:
            response = await call_next(request)

    if csrf_report is not None:
        response.headers[REPORT_HEADER] = csrf_report

    # Token verification remains non-enforcing.
    # Missing or invalid tokens do not block existing writes.
    try:
        prepare_html_cookie(request, response)
    except (OSError, ValueError):
        response = PlainTextResponse(
            "CSRF signing key unavailable.",
            status_code=503,
        )

    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["X-Content-Type-Options"] = "nosniff"

    # Endpoint-specific policies, especially CSV exports,
    # take precedence over this conservative default.
    if (
        not request.url.path.startswith("/static/")
        and "cache-control" not in response.headers
    ):
        response.headers["Cache-Control"] = "private, no-store"

    return response


app.mount("/static", StaticFiles(directory=config.BASE_DIR / "static"), name="static")

for module in (dashboard, compounds, purchases, vials, coas, doses, supplies, vitals, labs, protocols, pages, pk, calendar, backups, search, inventory_intelligence, health_timeline, health_insights, exports, reliability, blends, vendor_prices):
    app.include_router(module.router)

app.include_router(food.router)
app.include_router(food_quick375.router)
app.include_router(food_bundle376.router)
app.include_router(food_manage377.router)
app.include_router(food_review378.router)
app.include_router(food_week379.router)
app.include_router(food_search380.router)
app.include_router(session_login385.router)
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

# Release 105-112: read-only workflow hub
from .routers import workflow_hub
app.include_router(workflow_hub.router)

# Release 113-120: read-only protocol inventory coverage
from .routers import protocol_coverage
app.include_router(protocol_coverage.router)

# Release 121-128: read-only inventory forecast
from .routers import inventory_forecast
app.include_router(inventory_forecast.router)

# Release 129-136: read-only forecast horizons
from .routers import forecast_horizons
app.include_router(forecast_horizons.router)

# Release 137-144: shared-stock forecast audit
from .routers import forecast_audit
app.include_router(forecast_audit.router)

# Release 145-152: scheduled inventory forecast
from .routers import scheduled_forecast
app.include_router(scheduled_forecast.router)

# Release 153-160: unified read-only planning hub
from .routers import planning_hub
app.include_router(planning_hub.router)

# Release 161-168: read-only future expiration exposure
from .routers import expiry_exposure
app.include_router(expiry_exposure.router)

# Release 177-184: FEFO forecast
from .routers import fefo_forecast
app.include_router(fefo_forecast.router)

# TRACKER_RELEASE_201_208
from .routers import planning_priorities
app.include_router(planning_priorities.router)


# TRACKER_RELEASE_233_240
from .routers import inventory_data_quality
app.include_router(inventory_data_quality.router)

# Read-only replenishment review
from .routers import replenishment_review
app.include_router(replenishment_review.router)

# Read-only unified reconstitution calculator
from .routers import reconstitution_calculator
app.include_router(reconstitution_calculator.router)
