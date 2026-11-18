#!/usr/bin/env bash
# Ops 690: only stage and start a bounded detached DEV release worker.
# Nothing executes release tests or installation in the caller's SSH session.
set -Eeuo pipefail
umask 077
APP=/opt/tracker
REF=release/690-overview-card-density
OPS=ops/690-dev-deploy
BASE=ae8c75ef39ed26fa505be17e0d8b6152542cbf36
TARGET=6a8cd357e7e8925228d1a37c50572f93c4ec0943
WORKER_COMMIT=be06413136ee3520f420132693fbc16f8f88deec
WORKER_PATH=scripts/tracker-release690-dev-detached-worker.sh
fail(){ echo "RELEASE_690_DEV_LAUNCH_ERROR=$*" >&2; exit 1; }
[[ "$(id -u)" == 0 && "$(hostname -s)" == tracker-dev ]] || fail "Only root on tracker-dev"
cd "$APP"
export GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=safe.directory GIT_CONFIG_VALUE_0="$APP"
[[ "$(git branch --show-current)" == main && -z "$(git status --porcelain)" ]] ||
  fail "Require clean installed DEV main"
[[ "$(git rev-parse HEAD)" == "$BASE" ]] || fail "Require DEV Release 689 baseline"
systemctl is-active --quiet tracker || fail "Tracker service is not active"
git fetch origin "refs/heads/$OPS:refs/remotes/origin/$OPS" "refs/heads/$REF:refs/remotes/origin/$REF"
git merge-base --is-ancestor "$WORKER_COMMIT" "refs/remotes/origin/$OPS" ||
  fail "Pinned worker commit not present in ops branch"
[[ "$(git rev-parse "refs/remotes/origin/$REF")" == "$TARGET" ]] ||
  fail "Candidate branch differs from qualified Release 690"
git merge-base --is-ancestor "$BASE" "$TARGET" ||
  fail "Qualified candidate not based on DEV release 689"
git diff --check "$BASE" "$TARGET"
EXPECTED="$(printf '%s\n' \
  app/static/css/tracker-overview-density690.css \
  app/templates/dashboard.html \
  scripts/tracker-preview690.sh \
  scripts/tracker-release-scoped690.sh \
  tests/test_overview_density690.py | LC_ALL=C sort)"
ACTUAL="$(git diff --name-only "$BASE" "$TARGET" | LC_ALL=C sort)"
[[ "$EXPECTED" == "$ACTUAL" ]] || fail "Unexpected changed files"
"$APP/.venv/bin/python" - <<'PY'
import ast, subprocess
source = subprocess.check_output(
    ["git", "show", "6a8cd357e7e8925228d1a37c50572f93c4ec0943:tests/test_overview_density690.py"],
    text=True,
)
ast.parse(source, filename="tests/test_overview_density690.py")
print("RELEASE_690_DEV_SYNTAX_PREFLIGHT=PASSED")
PY
STAGE="$(mktemp -d /tmp/tracker-690-dev-detached.XXXXXXXX)"
chmod 700 "$STAGE"
WORKER="$STAGE/worker.sh"
git show "$WORKER_COMMIT:$WORKER_PATH" > "$WORKER"
[[ "$(git hash-object "$WORKER")" == "$(git rev-parse "$WORKER_COMMIT:$WORKER_PATH")" ]] || {
  rm -rf -- "$STAGE"
  fail "Pinned worker file mismatch"
}
bash -n "$WORKER"
chmod 700 "$WORKER"
UNIT="tracker-dev690-$(date -u +%Y%m%d%H%M%S)-$$"
echo "RELEASE_690_DEV_LAUNCH_UNIT=$UNIT"
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
echo "RELEASE_690_DEV_LAUNCH=DETACHED"
echo "RELEASE_690_DEV_INSTALLATION=STARTED_NOT_VERIFIED"
echo "RELEASE_690_PROD_INSTALLATION=NOT_REQUESTED"
echo "RELEASE_690_DEV_JOURNAL=journalctl --no-pager -u $UNIT -o cat"
echo "RELEASE_690_DEV_SYSTEMD_STATE=systemctl show $UNIT -p ActiveState -p SubState -p Result -p ExecMainStatus"
echo "RELEASE_690_DEV_WORKER_STAGE=$STAGE"
