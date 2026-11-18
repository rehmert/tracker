#!/usr/bin/env bash
# Ops 689: only stage and start a bounded detached DEV release worker.
# Nothing executes release tests or installation in the caller's SSH session.
set -Eeuo pipefail
umask 077
APP=/opt/tracker
REF=release/689-workout-footnote-spacing
OPS=ops/689-dev-deploy
BASE=a55456b3c9e74e91dc35a7cd74579566c7a63355
TARGET=ae8c75ef39ed26fa505be17e0d8b6152542cbf36
WORKER_COMMIT=5d424247f4c7f21ad393ede8ef23c99e90c627e5
WORKER_PATH=scripts/tracker-release689-dev-detached-worker.sh
fail(){ echo "RELEASE_689_DEV_LAUNCH_ERROR=$*" >&2; exit 1; }
[[ "$(id -u)" == 0 && "$(hostname -s)" == tracker-dev ]] || fail "Only root on tracker-dev"
cd "$APP"
export GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=safe.directory GIT_CONFIG_VALUE_0="$APP"
[[ "$(git branch --show-current)" == main && -z "$(git status --porcelain)" ]] ||
  fail "Require clean installed DEV main"
[[ "$(git rev-parse HEAD)" == "$BASE" ]] || fail "Require DEV Release 688 baseline"
systemctl is-active --quiet tracker || fail "Tracker service is not active"
git fetch origin "refs/heads/$OPS:refs/remotes/origin/$OPS" "refs/heads/$REF:refs/remotes/origin/$REF"
git merge-base --is-ancestor "$WORKER_COMMIT" "refs/remotes/origin/$OPS" ||
  fail "Pinned worker commit not present in ops branch"
[[ "$(git rev-parse "refs/remotes/origin/$REF")" == "$TARGET" ]] ||
  fail "Candidate branch differs from qualified Release 689"
git merge-base --is-ancestor "$BASE" "$TARGET" ||
  fail "Qualified candidate not based on DEV release 688"
git diff --check "$BASE" "$TARGET"
EXPECTED="$(printf '%s\n' \
  app/static/css/tracker-workout-footnote689.css \
  app/templates/base.html \
  scripts/tracker-preview689.sh \
  scripts/tracker-release-scoped689.sh \
  tests/test_workout_footnote_spacing689.py | LC_ALL=C sort)"
ACTUAL="$(git diff --name-only "$BASE" "$TARGET" | LC_ALL=C sort)"
[[ "$EXPECTED" == "$ACTUAL" ]] || fail "Unexpected changed files"
"$APP/.venv/bin/python" - <<'PY'
import ast, subprocess
source = subprocess.check_output(
    ["git", "show", "ae8c75ef39ed26fa505be17e0d8b6152542cbf36:tests/test_workout_footnote_spacing689.py"],
    text=True,
)
ast.parse(source, filename="tests/test_workout_footnote_spacing689.py")
print("RELEASE_689_DEV_SYNTAX_PREFLIGHT=PASSED")
PY
STAGE="$(mktemp -d /tmp/tracker-689-dev-detached.XXXXXXXX)"
chmod 700 "$STAGE"
WORKER="$STAGE/worker.sh"
git show "$WORKER_COMMIT:$WORKER_PATH" > "$WORKER"
[[ "$(git hash-object "$WORKER")" == "$(git rev-parse "$WORKER_COMMIT:$WORKER_PATH")" ]] || {
  rm -rf -- "$STAGE"
  fail "Pinned worker file mismatch"
}
bash -n "$WORKER"
chmod 700 "$WORKER"
UNIT="tracker-dev689-$(date -u +%Y%m%d%H%M%S)-$$"
echo "RELEASE_689_DEV_LAUNCH_UNIT=$UNIT"
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
echo "RELEASE_689_DEV_LAUNCH=DETACHED"
echo "RELEASE_689_DEV_INSTALLATION=STARTED_NOT_VERIFIED"
echo "RELEASE_689_PROD_INSTALLATION=NOT_REQUESTED"
echo "RELEASE_689_DEV_JOURNAL=journalctl --no-pager -u $UNIT -o cat"
echo "RELEASE_689_DEV_SYSTEMD_STATE=systemctl show $UNIT -p ActiveState -p SubState -p Result -p ExecMainStatus"
echo "RELEASE_689_DEV_WORKER_STAGE=$STAGE"
