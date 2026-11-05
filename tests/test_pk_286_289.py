import sqlite3
from fastapi.testclient import TestClient
from app import config
from app.main import app
from app.csrf_policy289 import reject_write
from app.csrf_runtime import COOKIE_NAME
from app.routers.sqlite_viewer import _tables,_safe_columns


def test_csrf_enforcement_is_explicitly_opt_in():
    assert not reject_write('POST','missing','0')
    assert reject_write('POST','missing','1')
    assert reject_write('PATCH','invalid','1')
    assert not reject_write('POST','valid','1')
    assert not reject_write('GET',None,'1')


def test_csrf_enforcement_real_middleware(monkeypatch,tmp_path):
    monkeypatch.setattr(config,'AUTH_USER','')
    monkeypatch.setattr(config,'AUTH_PASS','')
    monkeypatch.setattr(config,'DATA_DIR',tmp_path)
    monkeypatch.setenv('TRACKER_CSRF_ENFORCE','1')
    with TestClient(app) as client:
        page=client.get('/labs')
        assert page.status_code==200
        token=page.cookies[COOKIE_NAME]
        denied=client.post('/compounds',data={'name':''})
        assert denied.status_code==403
        allowed=client.post('/compounds',data={'name':''},headers={'X-Tracker-CSRF':token})
        assert allowed.status_code==422


def test_database_viewer_is_allowlisted():
    db=sqlite3.connect(':memory:')
    db.row_factory=sqlite3.Row
    db.execute('CREATE TABLE compounds (id INTEGER, name TEXT, notes TEXT)')
    db.execute('CREATE TABLE vendor_site_credentials (id INTEGER, secret TEXT)')
    assert _tables(db)==['compounds']
    assert _safe_columns('compounds',['id','name','notes'])==['id','name']
    assert _safe_columns('unknown',['id'])==[]
    db.close()
