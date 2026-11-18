#!/usr/bin/env bash
# Release 679 isolated visual audit: localhost, disposable data, no installation.
set -Eeuo pipefail
umask 077
APP=/opt/tracker
TARGET=a24bb47e0193ce7ca61b6d095ab055f37082aaf7
PY="$APP/.venv/bin/python"
die(){ echo "VISUAL679_ERROR=$*" >&2; exit 1; }
[[ "$(id -u)" == 0 && "$(hostname -s)" == tracker-dev ]] || die "Root on tracker-dev required"
[[ -x "$PY" ]] || die "Missing Python"
cd "$APP"
export GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=safe.directory GIT_CONFIG_VALUE_0="$APP"
[[ "$(git branch --show-current)" == main && -z "$(git status --porcelain)" ]] || die "Require clean installed checkout"
[[ "$(git rev-parse HEAD)" == "$TARGET" ]] || die "Installed DEV must be pinned Release 679"
ROOT="$(mktemp -d /tmp/tracker-679-visual.XXXXXXXX)"
QA="$ROOT/source"
PID=""
cleanup(){
 code=$?
 trap - EXIT
 if [[ -n "$PID" ]]; then kill "$PID" 2>/dev/null || true; wait "$PID" 2>/dev/null || true; fi
 if [[ -d "$QA" ]]; then git -C "$APP" worktree remove --force "$QA" >/dev/null 2>&1 || true; fi
 echo "VISUAL679_RESULTS=$ROOT"
 echo "VISUAL679_EXIT_STATUS=$code"
 exit "$code"
}
trap cleanup EXIT
chmod 700 "$ROOT"
git worktree add --detach "$QA" "$TARGET"
export GIT_CONFIG_COUNT=2 GIT_CONFIG_KEY_0=safe.directory GIT_CONFIG_VALUE_0="$APP" GIT_CONFIG_KEY_1=safe.directory GIT_CONFIG_VALUE_1="$QA"
SRC="$APP/app/static/vendor/htmx.min.js"
DST="$QA/app/static/vendor/htmx.min.js"
[[ -f "$SRC" && ! -L "$SRC" ]] || die "Local trusted HTMX unavailable"
mkdir -p "$(dirname "$DST")"
if [[ ! -e "$DST" ]]; then install -m 644 "$SRC" "$DST"; else cmp -s "$SRC" "$DST" || die "Vendor mismatch"; fi
mkdir -m 700 "$ROOT/data" "$ROOT/images"
PORT="$("$PY" - <<'PY'
import socket
with socket.socket() as s:
 s.bind(('127.0.0.1',0))
 print(s.getsockname()[1])
PY
)"
BASE="http://127.0.0.1:$PORT"
(
 cd "$QA"
 env -i HOME=/root PATH=/usr/local/bin:/usr/bin:/bin PYTHONPATH="$QA" TRACKER_DATA_DIR="$ROOT/data" TRACKER_INSTANCE=DEV PYTHONDONTWRITEBYTECODE=1 \
 "$PY" -B -m uvicorn app.main:app --host 127.0.0.1 --port "$PORT" --app-dir "$QA"
) >"$ROOT/server.log" 2>&1 &
PID=$!
"$PY" - "$BASE" "$PID" <<'PY'
import os,sys,time,urllib.request
url,pid=sys.argv[1],int(sys.argv[2])
opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
for i in range(60):
 try:
  os.kill(pid,0)
  with opener.open(url+'/healthz',timeout=2) as r:
   if r.status==200 and b'"ok":true' in r.read().replace(b' ',b''): break
 except (OSError,RuntimeError): pass
 time.sleep(.5)
else: raise SystemExit('ISOLATED_SERVER_NOT_READY')
print('VISUAL679_SERVER=ISOLATED_READY')
PY
"$PY" - "$BASE" "$ROOT/images" <<'PY'
import json,os,sys
from pathlib import Path
from playwright.sync_api import sync_playwright
base=sys.argv[1]
out=Path(sys.argv[2])
routes={'overview':'/','today':'/mobile','food':'/food','doses':'/doses','workouts':'/workouts','gym':'/workouts/quick'}
results=[]
with sync_playwright() as p:
 b=p.chromium.launch(headless=True,executable_path=os.environ.get('TRACKER_TEST_CHROMIUM_PATH') or None)
 try:
  for name,path in routes.items():
   for theme in ('light','dark'):
    for view,width,height in (('phone',390,844),('desktop',1280,900)):
     context=b.new_context(viewport={'width':width,'height':height},color_scheme=theme)
     try:
      page=context.new_page()
      errors=[]
      page.on('pageerror',lambda e:errors.append(str(e).splitlines()[0][:100]))
      response=page.goto(base+path,wait_until='domcontentloaded',timeout=20000)
      page.wait_for_timeout(300)
      data=page.evaluate("""() => ({
       title:document.title,
       hasMain:!!document.querySelector('#main-content'),
       overflow:document.documentElement.scrollWidth>innerWidth+1,
       missingStyles:[...document.querySelectorAll('link[rel="stylesheet"]')].filter(x=>!x.sheet).length,
       found679:!![...document.querySelectorAll('link[rel="stylesheet"]')].find(x=>x.href.includes('tracker-ui-foundation679.css')),
       tinyTargets:[...document.querySelectorAll('#main-content button,#main-content a')].filter(x=>{
        const r=x.getBoundingClientRect();return r.width>0&&r.height>0&&(r.width<30||r.height<30);
       }).length
      })""")
      # Diagnostic only: no link destinations, labels, content, or records emitted.
      small=page.evaluate("""() => [...document.querySelectorAll('#main-content button,#main-content a')]
       .filter(x=>{const r=x.getBoundingClientRect();return r.width>0&&r.height>0&&(r.width<30||r.height<30)})
       .map(x=>{const r=x.getBoundingClientRect(),s=getComputedStyle(x);
        return {tag:x.tagName.toLowerCase(),id:x.id.slice(0,70),
         classes:[...x.classList].slice(0,5).map(v=>v.slice(0,45)),
         width:Math.round(r.width),height:Math.round(r.height),
         visibility:s.visibility,role:x.getAttribute('role')||''};})
       .slice(0,25)""")
      record=dict(page=name,theme=theme,viewport=view,status=response.status if response else 0,errors=errors[:3],smallTargets=small,**data)
      if record['status']==200 and data['hasMain']:
       page.screenshot(path=str(out/f'{name}-{view}-{theme}.png'),full_page=True,animations='disabled')
     except Exception as e:
      record=dict(page=name,theme=theme,viewport=view,error=str(e).splitlines()[0][:160])
     finally:
      context.close()
     results.append(record)
     print('VISUAL679_PAGE='+json.dumps(record,separators=(',',':')),flush=True)
 finally: b.close()
(out.parent/'summary.json').write_text(json.dumps(results,indent=2)+'\n')
flagged=[r for r in results if r.get('status')!=200 or not r.get('hasMain') or r.get('overflow') or r.get('missingStyles') or not r.get('found679') or r.get('errors') or r.get('error')]
print('VISUAL679_CHECKED='+str(len(results)))
print('VISUAL679_FLAGGED='+str(len(flagged)))
print('VISUAL679_RESULT='+('REVIEW_FLAGS_PRESENT' if flagged else 'AUTOMATED_CHECKS_PASSED_MANUAL_REVIEW_REQUIRED'))
PY
echo "VISUAL679_LIVE_DATA=NOT_ACCESSED"
echo "VISUAL679_PROD=UNTOUCHED"
echo "VISUAL679_FULL_SUITE=NOT_RUN"
