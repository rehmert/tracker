import importlib.util
from pathlib import Path

spec=importlib.util.spec_from_file_location("bench",Path(__file__).resolve().parents[1]/"scripts/tracker_benchmark800.py")
bench=importlib.util.module_from_spec(spec)
spec.loader.exec_module(bench)


def test_statistics():
    result=bench.summarize([(1,2,.1),(2,4,.2),(100,6,.3)])
    assert result["median_ms"]==2
    assert result["p95_ms"]==100
    assert result["median_queries"]==4
    assert result["median_sql_ms"]==.2


def test_installed_testclient_auth_contract():
    from fastapi import FastAPI, Request
    from fastapi.testclient import TestClient
    app = FastAPI()
    @app.get("/")
    def endpoint(request: Request):
        return {"auth": request.headers.get("authorization")}
    with TestClient(app, follow_redirects=False) as client:
        assert client.get("/", auth=("benchmark","synthetic-only")).json()["auth"].startswith("Basic ")
