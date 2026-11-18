#!/usr/bin/env bash
# DEV-only installer for additive PROD uploads pull each minute.
# Source data on PROD is read-only; no database copy, delete or app deploy.
set -Eeuo pipefail
umask 077
APP=/opt/tracker
OPS=ops/688-prod-upload-mirror
PY="$APP/.venv/bin/python"
BASE687=6c47f765e76d4e4609f1d36c06226f439b28334d
BASE688=a55456b3c9e74e91dc35a7cd74579566c7a63355
SERVICE=tracker-prod-uploads-to-dev.service
TIMER=tracker-prod-uploads-to-dev.timer
INSTALL_DIR=/etc/systemd/system
fail(){ echo "UPLOAD_MIRROR_INSTALL=FAILED: $*" >&2; exit 1; }
[[ $# == 1 && "$1" =~ ^[a-f0-9]{40}$ ]] || fail "Pinned operations commit SHA required"
OPS_SHA="$1"
[[ "$(id -u)" -eq 0 && "$(hostname -s)" == tracker-dev ]] || fail "Root on tracker-dev only"
command -v systemd-analyze >/dev/null || fail "systemd-analyze missing"
command -v rsync >/dev/null || fail "rsync missing on DEV"
command -v ssh >/dev/null || fail "ssh client missing"
[[ -x "$PY" ]] || fail "Tracker Python missing"
[[ -d "$APP/data/uploads" && ! -L "$APP/data/uploads" ]] || fail "DEV uploads missing or symlinked"
[[ -f "$APP/data/tracker.db" && ! -L "$APP/data/tracker.db" ]] || fail "DEV DB unavailable"
"$PY" - <<'PY'
from pathlib import Path
root = Path("/opt/tracker/data/uploads")
for item in root.rglob("*"):
    if item.is_symlink():
        raise SystemExit("UPLOAD_MIRROR_INSTALL=FAILED: DEV uploads contains symlink")
print("UPLOAD_MIRROR_DEV_PATHS=NO_SYMLINKS")
PY
cd "$APP"
export GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=safe.directory GIT_CONFIG_VALUE_0="$APP"
[[ "$(git branch --show-current)" == main && -z "$(git status --porcelain)" ]] || fail "DEV must have clean main checkout"
HEAD="$(git rev-parse HEAD)"
[[ "$HEAD" == "$BASE687" || "$HEAD" == "$BASE688" ]] ||
  fail "DEV installed SHA is not qualified Release 687 or 688"
"$PY" "$APP/scripts/tracker-instance-check653.py" --config /etc/tracker.env ||
  fail "DEV identity check failed"
[[ -f "$APP/scripts/tracker-prod-uploads-to-dev645.sh" && ! -L "$APP/scripts/tracker-prod-uploads-to-dev645.sh" ]] ||
  fail "Existing additive reconciliation script unavailable"
[[ "$(git hash-object "$APP/scripts/tracker-prod-uploads-to-dev645.sh")" ==
   "$(git rev-parse "$HEAD:scripts/tracker-prod-uploads-to-dev645.sh")" ]] ||
  fail "Installed reconciliation script differs from qualified commit"
bash -n "$APP/scripts/tracker-prod-uploads-to-dev645.sh"
for name in "$SERVICE" "$TIMER"; do
  [[ ! -e "$INSTALL_DIR/$name" && ! -L "$INSTALL_DIR/$name" ]] ||
    fail "Existing $name found: refusing to overwrite"
done
echo "UPLOAD_MIRROR_SOURCE=EXISTING_ADDITIVE_645"
echo "UPLOAD_MIRROR_DIRECTION=PROD_TO_DEV_ONLY"
echo "UPLOAD_MIRROR_PROD_SSH=root@tracker-prod"
# SSH -n is deliberate: no SSH command can consume the calling shell's stdin.
timeout 25 ssh -n -T -o BatchMode=yes -o ConnectTimeout=8 \
  -o StrictHostKeyChecking=yes root@tracker-prod \
  'test "$(hostname -s)" = tracker-prod && test -r /etc/tracker.env && command -v rsync >/dev/null' ||
  fail "Read-only PROD SSH identity/rsync preflight failed"
echo "UPLOAD_MIRROR_PROD_SSH_PREFLIGHT=PASSED"

git fetch origin "refs/heads/$OPS:refs/remotes/origin/$OPS"
git merge-base --is-ancestor "$OPS_SHA" "refs/remotes/origin/$OPS" ||
  fail "Pinned ops commit not in fetched branch"
STAGE="$(mktemp -d /tmp/tracker-upload-mirror.XXXXXXXX)"
rollback=0
cleanup(){
  code=$?
  trap - EXIT
  if (( code != 0 && rollback == 1 )); then
    systemctl disable --now "$TIMER" >/dev/null 2>&1 || true
    rm -f -- "$INSTALL_DIR/$SERVICE" "$INSTALL_DIR/$TIMER"
    systemctl daemon-reload || true
    echo "UPLOAD_MIRROR_INSTALL=ROLLED_BACK"
  fi
  rm -rf -- "$STAGE"
  exit "$code"
}
trap cleanup EXIT
mkdir -p "$STAGE/deploy" "$STAGE/scripts" "$STAGE/tests"
for path in "deploy/$SERVICE" "deploy/$TIMER" \
  "scripts/tracker-install-prod-upload-mirror688.sh" \
  "tests/test_prod_upload_mirror688.py"; do
  git show "$OPS_SHA:$path" > "$STAGE/$path" || fail "Missing pinned asset $path"
done
cp "$APP/scripts/tracker-prod-uploads-to-dev645.sh" "$STAGE/scripts/tracker-prod-uploads-to-dev645.sh"
bash -n "$STAGE/scripts/tracker-install-prod-upload-mirror688.sh"
bash -n "$STAGE/scripts/tracker-prod-uploads-to-dev645.sh"
"$PY" -m py_compile "$STAGE/tests/test_prod_upload_mirror688.py"
"$PY" -m pytest -q --tb=short "$STAGE/tests/test_prod_upload_mirror688.py" ||
  fail "Scoped timer safety tests failed"
systemd-analyze verify "$STAGE/deploy/$SERVICE" "$STAGE/deploy/$TIMER" ||
  fail "systemd unit verification failed"
echo "UPLOAD_MIRROR_SCOPE=UNIT_TESTS_ONLY_NO_FULL_SUITE"
echo "UPLOAD_MIRROR_UNIT_PREFLIGHT=PASSED"

# Avoid installing units concurrently with an app release or DB replication.
exec 8>/run/lock/tracker-db-sync.lock
flock -n 8 || fail "Release or database replication active; retry after completion"
rollback=1
install -m 0644 "$STAGE/deploy/$SERVICE" "$INSTALL_DIR/$SERVICE"
install -m 0644 "$STAGE/deploy/$TIMER" "$INSTALL_DIR/$TIMER"
systemctl daemon-reload
flock -u 8
systemctl enable --now "$TIMER" ||
  fail "Could not enable minute timer"
# Start the first full reconciliation asynchronously, not under SSH.
systemctl start --no-block "$SERVICE" ||
  fail "Could not launch initial background reconciliation"
rollback=0
echo "UPLOAD_MIRROR_INSTALL=SUCCESS"
echo "UPLOAD_MIRROR_TIMER=ENABLED_MINUTELY"
echo "UPLOAD_MIRROR_FIRST_RUN=LAUNCHED_NOT_YET_VERIFIED"
echo "UPLOAD_MIRROR_JOURNAL=journalctl --no-pager -u $SERVICE -n 100 -o cat"
echo "UPLOAD_MIRROR_TIMER_STATUS=systemctl list-timers $TIMER --no-pager"
echo "PROD_APP=UNMODIFIED"
echo "DEV_APP=UNMODIFIED"
