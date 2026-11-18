#!/usr/bin/env bash
# Release 680 isolated visual audit: localhost, disposable data, no installation.
set -Eeuo pipefail
umask 077
APP=/opt/tracker
TARGET=a8bd5a5a09a3e8274944b24e366a8b4840bcb9df
PY="$APP/.venv/bin/python"
die(){ echo "VISUAL680_ERROR=$*" >&2; exit 1; }
[[ "$(id -u)" == 0 && "$(hostname -s)" == tracker-dev ]] || die "Root on tracker-dev required"
[[ -x "$PY" ]] || die "Missing Python"
cd "$APP"
export GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=safe.directory GIT_CONFIG_VALUE_0="$APP"
[[ "$(git branch --show-current)" == main && -z "$(git status --porcelain)" ]] || die "Require clean installed checkout"
[[ "$(git rev-parse HEAD)" == "$TARGET" ]] || die "Installed DEV must be pinned Release 680"
ROOT="$(mktemp -d /tmp/tracker-680-visual.XXXXXXXX)"
QA="$ROOT/source"
PID=""
cleanup(){
 code=$?
 trap - EXIT
 if [[ -n "$PID" ]]; then kill "$PID" 2>/dev/null || true; wait "$PID" 2>/dev/null || true; fi
 if [[ -d "$QA" ]]; then git -C "$APP" worktree remove --force "$QA" >/dev/null 2>&1 || true; fi
 echo "VISUAL680_RESULTS=$ROOT"
 echo "VISUAL680_EXIT_STATUS=$code"
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
print('VISUAL680_SERVER=ISOLATED_READY')
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
       found680:!![...document.querySelectorAll('link[rel="stylesheet"]')].find(x=>x.href.includes('tracker-ui-foundation680.css')),
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
      toggle_dims=page.evaluate("""() => [...document.querySelectorAll('#main-content .tracker-explanation598-toggle')]
       .filter(x=>x.getClientRects().length&&getComputedStyle(x).visibility!=='hidden')
       .map(x=>{const r=x.getBoundingClientRect();return {width:Math.round(r.width),height:Math.round(r.height)};})""")
      undersized_toggles=[x for x in toggle_dims if x['width']<44 or x['height']<44]
      record=dict(page=name,theme=theme,viewport=view,status=response.status if response else 0,
                  errors=errors[:3],smallTargets=small,explanationToggles=len(toggle_dims),
                  undersizedExplanationToggles=undersized_toggles,**data)
      if record['status']==200 and data['hasMain']:
       page.screenshot(path=str(out/f'{name}-{view}-{theme}.png'),full_page=True,animations='disabled')
     except Exception as e:
      record=dict(page=name,theme=theme,viewport=view,error=str(e).splitlines()[0][:160])
     finally:
      context.close()
     results.append(record)
     print('VISUAL680_PAGE='+json.dumps(record,separators=(',',':')),flush=True)
 finally: b.close()
(out.parent/'summary.json').write_text(json.dumps(results,indent=2)+'\n')
flagged=[r for r in results if r.get('status')!=200 or not r.get('hasMain') or r.get('overflow') or r.get('missingStyles') or not r.get('found680') or r.get('undersizedExplanationToggles') or r.get('errors') or r.get('error')]
print('VISUAL680_CHECKED='+str(len(results)))
print('VISUAL680_TOGGLES_CHECKED='+str(sum(r.get('explanationToggles',0) for r in results)))
print('VISUAL680_UNDERSIZED_EXPLANATION_TOGGLES='+str(sum(len(r.get('undersizedExplanationToggles',[])) for r in results)))
print('VISUAL680_FLAGGED='+str(len(flagged)))
print('VISUAL680_RESULT='+('REVIEW_FLAGS_PRESENT' if flagged else 'AUTOMATED_CHECKS_PASSED_MANUAL_REVIEW_REQUIRED'))
PY
echo "VISUAL680_LIVE_DATA=NOT_ACCESSED"
echo "VISUAL680_PROD=UNTOUCHED"
echo "VISUAL680_FULL_SUITE=NOT_RUN"
