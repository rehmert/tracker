#!/usr/bin/env bash
# Ops 688: only stage and start a bounded detached DEV release worker.
# Nothing executes release tests or installation in the caller's SSH session.
set -Eeuo pipefail
umask 077
APP=/opt/tracker
REF=release/688-dashboard-polish
OPS=ops/688-dev-deploy
BASE=6c47f765e76d4e4609f1d36c06226f439b28334d
TARGET=a55456b3c9e74e91dc35a7cd74579566c7a63355
WORKER_COMMIT=1fde6ab029e07697cd8193f280ffababf73443b0
WORKER_PATH=scripts/tracker-release688-dev-detached-worker.sh
fail(){ echo "RELEASE_688_DEV_LAUNCH_ERROR=$*" >&2; exit 1; }
[[ "$(id -u)" == 0 && "$(hostname -s)" == tracker-dev ]] || fail "Only root on tracker-dev"
cd "$APP"
export GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=safe.directory GIT_CONFIG_VALUE_0="$APP"
[[ "$(git branch --show-current)" == main && -z "$(git status --porcelain)" ]] ||
  fail "Require clean installed DEV main"
[[ "$(git rev-parse HEAD)" == "$BASE" ]] || fail "Require DEV Release 687 baseline"
systemctl is-active --quiet tracker || fail "Tracker service is not active"
git fetch origin "refs/heads/$OPS:refs/remotes/origin/$OPS" "refs/heads/$REF:refs/remotes/origin/$REF"
git merge-base --is-ancestor "$WORKER_COMMIT" "refs/remotes/origin/$OPS" ||
  fail "Pinned worker commit not present in ops branch"
[[ "$(git rev-parse "refs/remotes/origin/$REF")" == "$TARGET" ]] ||
  fail "Candidate branch differs from qualified Release 688"
git merge-base --is-ancestor "$BASE" "$TARGET" ||
  fail "Qualified candidate not based on DEV release 687"
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
[[ "$EXPECTED" == "$ACTUAL" ]] || fail "Unexpected changed files"
"$APP/.venv/bin/python" - <<'PY'
import ast, subprocess
for path in (
    "tests/test_dashboard_polish688.py",
    "tests/test_workout_activity_cards_browser678.py",
):
    source = subprocess.check_output(
        ["git", "show", "a55456b3c9e74e91dc35a7cd74579566c7a63355:" + path], text=True
    )
    ast.parse(source, filename=path)
print("RELEASE_688_DEV_SYNTAX_PREFLIGHT=PASSED")
PY
STAGE="$(mktemp -d /tmp/tracker-688-dev-detached.XXXXXXXX)"
chmod 700 "$STAGE"
WORKER="$STAGE/worker.sh"
git show "$WORKER_COMMIT:$WORKER_PATH" > "$WORKER"
[[ "$(git hash-object "$WORKER")" == "$(git rev-parse "$WORKER_COMMIT:$WORKER_PATH")" ]] || {
  rm -rf -- "$STAGE"
  fail "Pinned worker file mismatch"
}
bash -n "$WORKER"
chmod 700 "$WORKER"
UNIT="tracker-dev688-$(date -u +%Y%m%d%H%M%S)-$$"
echo "RELEASE_688_DEV_LAUNCH_UNIT=$UNIT"
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
echo "RELEASE_688_DEV_LAUNCH=DETACHED"
echo "RELEASE_688_DEV_INSTALLATION=STARTED_NOT_VERIFIED"
echo "RELEASE_688_PROD_INSTALLATION=NOT_REQUESTED"
echo "RELEASE_688_DEV_JOURNAL=journalctl --no-pager -u $UNIT -o cat"
echo "RELEASE_688_DEV_SYSTEMD_STATE=systemctl show $UNIT -p ActiveState -p SubState -p Result -p ExecMainStatus"
echo "RELEASE_688_DEV_WORKER_STAGE=$STAGE"
