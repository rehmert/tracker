from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.staticfiles import StaticFiles

from . import config, models  # noqa: F401  (models import registers tables)
from .db import Base, engine
from .routers import coas, compounds, dashboard, doses, protocols, purchases, vials
from .security import require_auth


@asynccontextmanager
async def lifespan(_app: FastAPI):
    Base.metadata.create_all(engine)
    yield


app = FastAPI(title="Peptide & TRT Ledger", dependencies=[Depends(require_auth)],
              lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)
app.mount("/static", StaticFiles(directory=config.BASE_DIR / "static"), name="static")

for module in (dashboard, compounds, purchases, vials, coas, doses, protocols):
    app.include_router(module.router)


@app.get("/healthz", include_in_schema=False)
def healthz():
    return {"ok": True}
