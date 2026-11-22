#!/usr/bin/env bash
# Release 751 reversible systemd strict-CSRF rollout (tracker-dev only).
set -Eeuo pipefail
umask 077
APP=/opt/tracker
DIR=/etc/systemd/system/tracker.service.d
DROP="$DIR/95-tracker-csrf751.conf"
ENV_FILE=/etc/tracker-csrf751.env
MARKER='Tracker Release 751 DEV strict CSRF'
MODE="$(printf '%s' "$1")"
die(){ echo "STRICT_CSRF_751_BLOCKED=$*" >&2; exit 1; }
[[ "$(id -u)" == 0 && "$(hostname -s)" == tracker-dev ]] ||
 die "Root on tracker-dev only"
[[ -x "$APP/.venv/bin/python" && -f /etc/tracker.env ]] ||
 die "Configured DEV service missing"
systemctl cat tracker.service >/dev/null || die "Service not found"
case "$MODE" in enable|disable|status) ;; *) die "Expected enable|disable|status";; esac
csrf_flag(){
 local pid
 pid="$(systemctl show tracker.service -p MainPID --value)"
 [[ "$pid" =~ ^[1-9][0-9]*$ ]] || return 1
 "$APP/.venv/bin/python" - "$pid" <<'PY'
import sys
from pathlib import Path
data=(Path("/proc")/sys.argv[1]/"environ").read_bytes().split(b"\x00")
values=[x.split(b"=",1)[1] for x in data if x.startswith(b"TRACKER_CSRF_ENFORCE=")]
if len(values)>1: raise SystemExit("Duplicate strict flag")
print(values[0].decode("ascii") if values else "UNSET")
PY
}
health(){
 systemctl is-active --quiet tracker.service
 "$APP/.venv/bin/python" - <<'PY'
from urllib.request import build_opener, ProxyHandler
op=build_opener(ProxyHandler({}))
with op.open("http://127.0.0.1:8000/healthz",timeout=8) as r:
 assert r.status==200 and b'"ok":true' in r.read().replace(b" ",b"")
PY
}
deny_probe(){
 "$APP/.venv/bin/python" - <<'PY'
from urllib.request import build_opener, ProxyHandler, Request
from urllib.error import HTTPError
op=build_opener(ProxyHandler({}))
req=Request("http://127.0.0.1:8000/pk/compounds",data=b'{}',method="POST",
            headers={"Content-Type":"application/json"})
try: op.open(req,timeout=8)
except HTTPError as err:
 if err.code==403 and b"CSRF token required" in err.read():
  print("HTTP_751_UNSIGNED_WRITE=DENIED")
 else: raise SystemExit("Unexpected unsigned write result")
else: raise SystemExit("Unsigned write not rejected")
PY
}
if [[ "$MODE" == status ]]; then
 health
 echo "STRICT_CSRF_751_DEV_LIVE_FLAG=$(csrf_flag)"
 if [[ -f "$DROP" ]]; then
  grep -Fqx "# $MARKER" "$DROP" || die "Unrecognized override"
  echo "STRICT_CSRF_751_DEV_CONFIG=INSTALLED"
 else
  echo "STRICT_CSRF_751_DEV_CONFIG=ABSENT"
 fi
 exit 0
fi
if [[ "$MODE" == disable ]]; then
 [[ -f "$DROP" && ! -L "$DROP" && -f "$ENV_FILE" && ! -L "$ENV_FILE" ]] ||
  die "No managed override to remove"
 grep -Fqx "# $MARKER" "$DROP" || die "Unrecognized override"
 [[ "$(cat "$ENV_FILE")" == "TRACKER_CSRF_ENFORCE=1" ]] ||
  die "Unrecognized flag file"
 rm -- "$DROP" "$ENV_FILE"
 systemctl daemon-reload
 systemctl restart tracker.service
 health
 [[ "$(csrf_flag)" != 1 ]] || die "Strict flag persisted"
 echo "STRICT_CSRF_751_DEV=DISABLED"
 exit 0
fi
# Enabling requires the passed/installed SHA; never change service on earlier release.
[[ $# == 2 && "$2" =~ ^[0-9a-f]{40}$ ]] || die "Exact installed SHA required"
TARGET="$2"
cd "$APP"
export GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=safe.directory
export GIT_CONFIG_VALUE_0="$APP"
[[ "$(git branch --show-current)" == main &&
   "$(git rev-parse HEAD)" == "$TARGET" &&
   -z "$(git status --porcelain)" ]] || die "Wrong or dirty DEV checkout"
health
[[ "$(csrf_flag)" != 1 ]] || die "Strict mode already active"
[[ ! -e "$DROP" && ! -L "$DROP" &&
   ! -e "$ENV_FILE" && ! -L "$ENV_FILE" ]] ||
 die "Existing CSRF override must not be replaced"
[[ ! -L "$DIR" ]] || die "Symlinked systemd override directory"
mkdir -p "$DIR"
STATE=0
on_exit(){
 local rc=$?
 trap - EXIT
 if ((STATE==1)); then
  echo "ROLLBACK_751=RESTORING_REPORT_ONLY"
  rm -f -- "$DROP" "$ENV_FILE"
  systemctl daemon-reload || true
  systemctl restart tracker.service || true
  if ! health || [[ "$(csrf_flag)" == 1 ]]; then
   echo "ROLLBACK_751=HOST_REVIEW_REQUIRED" >&2
  fi
 fi
 exit "$rc"
}
trap on_exit EXIT
printf 'TRACKER_CSRF_ENFORCE=1\n' > "$ENV_FILE"
chmod 0600 "$ENV_FILE"
STATE=1
printf '# %s\n[Service]\nEnvironmentFile=%s\n' "$MARKER" "$ENV_FILE" > "$DROP"
chmod 0644 "$DROP"
systemctl daemon-reload
systemctl restart tracker.service
health
[[ "$(csrf_flag)" == 1 ]] || die "Service strict setting was not applied"
deny_probe
STATE=2
trap - EXIT
echo "STRICT_CSRF_751_DEV=ENABLED"
echo "STRICT_CSRF_751_ROLLBACK=sudo bash /opt/tracker/scripts/tracker-csrf-dev751.sh disable"
