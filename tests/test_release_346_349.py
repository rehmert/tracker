"""CSRF middleware acceptance on pytest-isolated Tracker data."""
import subprocess

from fastapi.testclient import TestClient

from app import config
from app.main import app
from app.csrf_runtime import COOKIE_NAME
from app.csrf_reporting import REPORT_HEADER


def test_csrf_form_json_multipart_enforcement(monkeypatch,tmp_path):
    monkeypatch.setattr(config,'AUTH_USER','')
    monkeypatch.setattr(config,'AUTH_PASS','')
    monkeypatch.setattr(config,'DATA_DIR',tmp_path)
    monkeypatch.setenv('TRACKER_CSRF_ENFORCE','1')

    with TestClient(app) as client:
        home=client.get('/labs')
        assert home.status_code==200
        token=home.cookies[COOKIE_NAME]

        assert client.post(
            '/compounds',data={}
        ).status_code==403

        assert client.post(
            '/compounds',
            data={},
            headers={'X-Tracker-CSRF':'wrong'}
        ).status_code==403

        valid=client.post(
            '/compounds',
            data={},
            headers={'X-Tracker-CSRF':token}
        )
        assert valid.status_code==422
        assert valid.headers[REPORT_HEADER]=='valid'

        assert client.post(
            '/pk/what-if/preview',json={}
        ).status_code==403

        accepted=client.post(
            '/pk/what-if/preview',
            json={},
            headers={'X-Tracker-CSRF':token}
        )
        assert accepted.status_code==422
        assert accepted.headers[REPORT_HEADER]=='valid'

        assert client.post(
            '/compounds',
            files={'upload':('demo.pdf',b'%PDF-1.4')}
        ).status_code==403

        accepted=client.post(
            '/compounds',
            files={'upload':('demo.pdf',b'%PDF-1.4')},
            headers={'X-Tracker-CSRF':token}
        )
        assert accepted.status_code==422
        assert accepted.headers[REPORT_HEADER]=='valid'


def test_security_runner_has_valid_bash_syntax():
    result=subprocess.run(
        ['bash','-n','scripts/tracker-security-gate349.sh'],
        capture_output=True,
        text=True
    )
    assert result.returncode==0,result.stderr
