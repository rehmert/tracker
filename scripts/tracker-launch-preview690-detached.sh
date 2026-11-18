#!/usr/bin/env bash
# Ops 690: short SSH preflight, isolated tests only in detached bounded systemd.
set -Eeuo pipefail
umask 077
APP=/opt/tracker
BASE=ae8c75ef39ed26fa505be17e0d8b6152542cbf36
TARGET=6a8cd357e7e8925228d1a37c50572f93c4ec0943
OPS=ops/690-detached-preview
REF=release/690-overview-card-density
WORKER_SHA=45fc2b5fc2b0b0fb3b5f5bf9d8c109d74e5dc424
WORKER_PATH=scripts/tracker-preview690-detached-worker.sh
fail(){ echo "RELEASE_690_LAUNCH_ERROR=$*" >&2; exit 1; }
[[ "$(id -u)" -eq 0 && "$(hostname -s)" == tracker-dev ]] || fail "Root on tracker-dev required"
cd "$APP"
export GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=safe.directory GIT_CONFIG_VALUE_0="$APP"
[[ "$(git branch --show-current)" == main && -z "$(git status --porcelain)" ]] ||
  fail "Require clean installed DEV main"
[[ "$(git rev-parse HEAD)" == "$BASE" ]] || fail "Require installed DEV Release 689"
systemctl is-active --quiet tracker || fail "DEV Tracker inactive"
git fetch origin "refs/heads/$OPS:refs/remotes/origin/$OPS" "refs/heads/$REF:refs/remotes/origin/$REF"
git merge-base --is-ancestor "$WORKER_SHA" "refs/remotes/origin/$OPS" ||
  fail "Pinned worker not found in operations ref"
[[ "$(git rev-parse "refs/remotes/origin/$REF")" == "$TARGET" ]] ||
  fail "Candidate branch changed from pinned Release 690"
git merge-base --is-ancestor "$BASE" "$TARGET" || fail "Candidate not descendant of DEV 688"
git diff --check "$BASE" "$TARGET"
EXPECTED="$(printf '%s\n' \
  app/static/css/tracker-overview-density690.css \
  app/templates/dashboard.html \
  scripts/tracker-preview690.sh \
  scripts/tracker-release-scoped690.sh \
  tests/test_overview_density690.py | LC_ALL=C sort)"
ACTUAL="$(git diff --name-only "$BASE" "$TARGET" | LC_ALL=C sort)"
[[ "$EXPECTED" == "$ACTUAL" ]] || fail "Unexpected source files in candidate"
"$APP/.venv/bin/python" -c 'import ast,subprocess; ast.parse(subprocess.check_output(["git","show","6a8cd357e7e8925228d1a37c50572f93c4ec0943:tests/test_overview_density690.py"], text=True))'
for script in scripts/tracker-preview690.sh scripts/tracker-release-scoped690.sh; do
  git show "$TARGET:$script" | bash -n
done
echo "RELEASE_690_SYNTAX_PREFLIGHT=PASSED"
STAGE="$(mktemp -d /tmp/tracker-690-detached.XXXXXXXX)"
chmod 700 "$STAGE"
WORKER="$STAGE/worker.sh"
git show "$WORKER_SHA:$WORKER_PATH" > "$WORKER"
[[ "$(git hash-object "$WORKER")" == "$(git rev-parse "$WORKER_SHA:$WORKER_PATH")" ]] || {
  rm -rf -- "$STAGE"
  fail "Worker hash mismatch"
}
bash -n "$WORKER"
chmod 700 "$WORKER"
UNIT="tracker-preview690-$(date -u +%Y%m%d%H%M%S)-$$"
echo "RELEASE_690_LAUNCH_UNIT=$UNIT"
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
echo "RELEASE_690_LAUNCH=DETACHED"
echo "RELEASE_690_PREVIEW=STARTED_NOT_YET_QUALIFIED"
echo "RELEASE_690_JOURNAL=journalctl --no-pager -u $UNIT -o cat"
echo "RELEASE_690_STATE=systemctl show $UNIT -p ActiveState -p SubState -p Result -p ExecMainStatus"
echo "RELEASE_690_INSTALLATION=NOT_REQUESTED"
