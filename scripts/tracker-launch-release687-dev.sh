#!/usr/bin/env bash
# Ops 687: only stage and start a bounded detached DEV release worker.
# Nothing executes release tests or installation in the caller's SSH session.
set -Eeuo pipefail
umask 077
APP=/opt/tracker
REF=release/687-shortcuts-toolbar
OPS=ops/687-dev-deploy
BASE=6d6505403ec191df66977ea0fab9d1004f7a022f
TARGET=6c47f765e76d4e4609f1d36c06226f439b28334d
WORKER_COMMIT=1e9fdc191ba9cbb37a69f407a21d9570de76ad7b
WORKER_PATH=scripts/tracker-release687-dev-detached-worker.sh
fail(){ echo "RELEASE_687_DEV_LAUNCH_ERROR=$*" >&2; exit 1; }
[[ "$(id -u)" == 0 && "$(hostname -s)" == tracker-dev ]] || fail "Only root on tracker-dev"
cd "$APP"
export GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=safe.directory GIT_CONFIG_VALUE_0="$APP"
[[ "$(git branch --show-current)" == main && -z "$(git status --porcelain)" ]] ||
  fail "Require clean installed DEV main"
[[ "$(git rev-parse HEAD)" == "$BASE" ]] || fail "Require DEV Release 686 baseline"
systemctl is-active --quiet tracker || fail "Tracker service is not active"
git fetch origin "refs/heads/$OPS:refs/remotes/origin/$OPS" "refs/heads/$REF:refs/remotes/origin/$REF"
git merge-base --is-ancestor "$WORKER_COMMIT" "refs/remotes/origin/$OPS" ||
  fail "Pinned worker commit not present in ops branch"
[[ "$(git rev-parse "refs/remotes/origin/$REF")" == "$TARGET" ]] ||
  fail "Candidate branch differs from qualified Release 687"
git merge-base --is-ancestor "$BASE" "$TARGET" ||
  fail "Qualified candidate not based on DEV release 686"
git diff --check "$BASE" "$TARGET"
EXPECTED="$(printf '%s\n' \
  app/static/css/tracker-shortcuts-toolbar687.css \
  app/templates/base.html \
  scripts/tracker-preview687.sh \
  scripts/tracker-release-scoped687.sh \
  tests/test_shortcuts_toolbar687.py | LC_ALL=C sort)"
ACTUAL="$(git diff --name-only "$BASE" "$TARGET" | LC_ALL=C sort)"
[[ "$EXPECTED" == "$ACTUAL" ]] || fail "Unexpected changed files"
"$APP/.venv/bin/python" -c 'import ast,subprocess; ast.parse(subprocess.check_output(["git","show","6c47f765e76d4e4609f1d36c06226f439b28334d:tests/test_shortcuts_toolbar687.py"], text=True))'
echo "RELEASE_687_DEV_SYNTAX_PREFLIGHT=PASSED"
STAGE="$(mktemp -d /tmp/tracker-687-dev-detached.XXXXXXXX)"
chmod 700 "$STAGE"
WORKER="$STAGE/worker.sh"
git show "$WORKER_COMMIT:$WORKER_PATH" > "$WORKER"
[[ "$(git hash-object "$WORKER")" == "$(git rev-parse "$WORKER_COMMIT:$WORKER_PATH")" ]] || {
  rm -rf -- "$STAGE"
  fail "Pinned worker file mismatch"
}
bash -n "$WORKER"
chmod 700 "$WORKER"
UNIT="tracker-dev687-$(date -u +%Y%m%d%H%M%S)-$$"
echo "RELEASE_687_DEV_LAUNCH_UNIT=$UNIT"
if ! systemd-run --no-block --unit="$UNIT" \
  --property=MemoryAccounting=yes \
  --property=MemoryMax=2G \
  --property=TasksMax=96 \
  --property=CPUQuota=200% \
  --property=RuntimeMaxSec=1800 \
  --property=TimeoutStopSec=30 \
  -- /usr/bin/bash "$WORKER"; then
  rm -rf -- "$STAGE"
  fail "systemd failed to start worker"
fi
echo "RELEASE_687_DEV_LAUNCH=DETACHED"
echo "RELEASE_687_DEV_INSTALLATION=STARTED_NOT_VERIFIED"
echo "RELEASE_687_PROD_INSTALLATION=NOT_REQUESTED"
echo "RELEASE_687_DEV_JOURNAL=journalctl --no-pager -u $UNIT -o cat"
echo "RELEASE_687_DEV_SYSTEMD_STATE=systemctl show $UNIT -p ActiveState -p SubState -p Result -p ExecMainStatus"
echo "RELEASE_687_DEV_WORKER_STAGE=$STAGE"
