import subprocess

from fastapi.testclient import TestClient

from app import config
from app.main import app
from app.csrf_runtime import COOKIE_NAME
from app.csrf_reporting import REPORT_HEADER


def test_multipart_header_enforcement_gate(
    monkeypatch,tmp_path
):
    monkeypatch.setattr(config,'AUTH_USER','')
    monkeypatch.setattr(config,'AUTH_PASS','')
    monkeypatch.setattr(config,'DATA_DIR',tmp_path)
    monkeypatch.setenv('TRACKER_CSRF_ENFORCE','1')

    with TestClient(app) as client:
        token=client.get('/labs').cookies[COOKIE_NAME]

        invalid=client.post(
            '/compounds',
            files={'upload':('x.txt',b'x')}
        )
        assert invalid.status_code==403

        good=client.post(
            '/compounds',
            files={'upload':('x.txt',b'x')},
            headers={'X-Tracker-CSRF':token}
        )

        assert good.status_code==422
        assert good.headers[REPORT_HEADER]=='valid'


def test_browser_fetch_writes_get_token_without_cross_origin_leak():
    code=r'''
const fs=require('fs');
const vm=require('vm');

const source=fs.readFileSync(
  'app/static/js/tracker-csrf-browser.js','utf8'
);

const calls=[];
const window={
  fetch:async (input,init)=>{
    calls.push({input,init});
    return {ok:true};
  }
};

const document={
  cookie:'tracker_csrf_v1=v1.sample.valid',
  readyState:'loading',
  addEventListener:()=>{}
};

const location={
  href:'https://tracker.example/labs',
  origin:'https://tracker.example'
};

const context={
  window,document,location,Headers,Request,URL,
  HTMLFormElement:class {},
  MutationObserver:class {observe(){}}
};

vm.runInNewContext(source,context);

(async()=>{
  await window.fetch('/pk/scenarios',{
    method:'POST',
    headers:{'Content-Type':'application/json'}
  });

  await window.fetch('https://external.example/api',{
    method:'POST'
  });

  await window.fetch('/labs',{method:'GET'});

  if(calls.length!==3) {
    throw Error('Unexpected request count');
  }

  if(
    calls[0].init.headers.get('X-Tracker-CSRF')
      !=='v1.sample.valid'
  ) {
    throw Error('Missing local token');
  }

  if(calls[1].init.headers) {
    throw Error('Cross-origin token leakage');
  }

  if(calls[2].init.headers) {
    throw Error('GET modified');
  }

  console.log('PASS: Same-origin fetch CSRF behavior');
})().catch(error=>{
  console.error(error);
  process.exitCode=1;
});
'''
    subprocess.run(['node','-e',code],check=True)
