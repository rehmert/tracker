#!/usr/bin/env bash
# Ops 688: launch isolated browser qualification through detached bounded systemd.
# Never executes Playwright or application deployment within SSH.
set -Eeuo pipefail
umask 077
APP=/opt/tracker
BASE=6c47f765e76d4e4609f1d36c06226f439b28334d
TARGET=a55456b3c9e74e91dc35a7cd74579566c7a63355
OPS=ops/688-detached-preview
REF=release/688-dashboard-polish
WORKER_SHA=5abf5e09d6b4e01b7e10965dc51c65de0140a363
WORKER_PATH=scripts/tracker-preview688-detached-worker.sh
fail(){ echo "RELEASE_688_LAUNCH_ERROR=$*" >&2; exit 1; }
[[ "$(id -u)" -eq 0 && "$(hostname -s)" == tracker-dev ]] || fail "Root on tracker-dev required"
cd "$APP"
export GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=safe.directory GIT_CONFIG_VALUE_0="$APP"
[[ "$(git branch --show-current)" == main && -z "$(git status --porcelain)" ]] ||
  fail "Require clean installed DEV main"
[[ "$(git rev-parse HEAD)" == "$BASE" ]] || fail "Require installed DEV 687"
systemctl is-active --quiet tracker || fail "DEV Tracker inactive"
git fetch origin "refs/heads/$OPS:refs/remotes/origin/$OPS" "refs/heads/$REF:refs/remotes/origin/$REF"
git merge-base --is-ancestor "$WORKER_SHA" "refs/remotes/origin/$OPS" ||
  fail "Pinned worker not found in operations ref"
[[ "$(git rev-parse "refs/remotes/origin/$REF")" == "$TARGET" ]] ||
  fail "Candidate branch changed from pinned Release 688"
git merge-base --is-ancestor "$BASE" "$TARGET" || fail "Candidate not descendant of DEV 687"
git diff --check "$BASE" "$TARGET"
EXPECTED="$(printf '%s\n' \
  app/static/css/tracker-dashboard-polish688.css \
  app/templates/_workout_dashboard661.html \
  app/templates/base.html \
  app/templates/dashboard.html \
  scripts/tracker-preview688.sh \
  scripts/tracker-release-scoped688.sh \
  tests/test_dashboard_polish688.py \
  tests/test_workout_activity_cards_browser678.py | LC_ALL=C sort)"
ACTUAL="$(git diff --name-only "$BASE" "$TARGET" | LC_ALL=C sort)"
[[ "$EXPECTED" == "$ACTUAL" ]] || fail "Unexpected source files in candidate"
"$APP/.venv/bin/python" -c 'import ast,subprocess; ast.parse(subprocess.check_output(["git","show","a55456b3c9e74e91dc35a7cd74579566c7a63355:tests/test_dashboard_polish688.py"], text=True))'
for script in scripts/tracker-preview688.sh scripts/tracker-release-scoped688.sh; do
  git show "$TARGET:$script" | bash -n
done
echo "RELEASE_688_SYNTAX_PREFLIGHT=PASSED"
STAGE="$(mktemp -d /tmp/tracker-688-detached.XXXXXXXX)"
chmod 700 "$STAGE"
WORKER="$STAGE/worker.sh"
git show "$WORKER_SHA:$WORKER_PATH" > "$WORKER"
[[ "$(git hash-object "$WORKER")" == "$(git rev-parse "$WORKER_SHA:$WORKER_PATH")" ]] || {
  rm -rf -- "$STAGE"
  fail "Worker hash mismatch"
}
bash -n "$WORKER"
chmod 700 "$WORKER"
UNIT="tracker-preview688-$(date -u +%Y%m%d%H%M%S)-$$"
echo "RELEASE_688_LAUNCH_UNIT=$UNIT"
if ! systemd-run --no-block --unit="$UNIT" \
  --property=MemoryAccounting=yes \
  --property=MemoryMax=2G \
  --property=TasksMax=96 \
  --property=CPUQuota=200% \
  --property=RuntimeMaxSec=900 \
  --property=TimeoutStopSec=15 \
  -- /usr/bin/bash "$WORKER"; then
  rm -rf -- "$STAGE"
  fail "Detached unit launch failed"
fi
echo "RELEASE_688_LAUNCH=DETACHED"
echo "RELEASE_688_PREVIEW=STARTED_NOT_YET_QUALIFIED"
echo "RELEASE_688_JOURNAL=journalctl --no-pager -u $UNIT -o cat"
echo "RELEASE_688_STATE=systemctl show $UNIT -p ActiveState -p SubState -p Result -p ExecMainStatus"
echo "RELEASE_688_INSTALLATION=NOT_REQUESTED"
