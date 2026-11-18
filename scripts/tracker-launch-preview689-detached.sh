#!/usr/bin/env bash
# Ops 689: short SSH preflight, isolated tests only in detached bounded systemd.
set -Eeuo pipefail
umask 077
APP=/opt/tracker
BASE=a55456b3c9e74e91dc35a7cd74579566c7a63355
TARGET=ae8c75ef39ed26fa505be17e0d8b6152542cbf36
OPS=ops/689-detached-preview
REF=release/689-workout-footnote-spacing
WORKER_SHA=52926b52ab85e34f80f616def1dca91547b55127
WORKER_PATH=scripts/tracker-preview689-detached-worker.sh
fail(){ echo "RELEASE_689_LAUNCH_ERROR=$*" >&2; exit 1; }
[[ "$(id -u)" -eq 0 && "$(hostname -s)" == tracker-dev ]] || fail "Root on tracker-dev required"
cd "$APP"
export GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=safe.directory GIT_CONFIG_VALUE_0="$APP"
[[ "$(git branch --show-current)" == main && -z "$(git status --porcelain)" ]] ||
  fail "Require clean installed DEV main"
[[ "$(git rev-parse HEAD)" == "$BASE" ]] || fail "Require installed DEV Release 688"
systemctl is-active --quiet tracker || fail "DEV Tracker inactive"
git fetch origin "refs/heads/$OPS:refs/remotes/origin/$OPS" "refs/heads/$REF:refs/remotes/origin/$REF"
git merge-base --is-ancestor "$WORKER_SHA" "refs/remotes/origin/$OPS" ||
  fail "Pinned worker not found in operations ref"
[[ "$(git rev-parse "refs/remotes/origin/$REF")" == "$TARGET" ]] ||
  fail "Candidate branch changed from pinned Release 689"
git merge-base --is-ancestor "$BASE" "$TARGET" || fail "Candidate not descendant of DEV 688"
git diff --check "$BASE" "$TARGET"
EXPECTED="$(printf '%s\n' \
  app/static/css/tracker-workout-footnote689.css \
  app/templates/base.html \
  scripts/tracker-preview689.sh \
  scripts/tracker-release-scoped689.sh \
  tests/test_workout_footnote_spacing689.py | LC_ALL=C sort)"
ACTUAL="$(git diff --name-only "$BASE" "$TARGET" | LC_ALL=C sort)"
[[ "$EXPECTED" == "$ACTUAL" ]] || fail "Unexpected source files in candidate"
"$APP/.venv/bin/python" -c 'import ast,subprocess; ast.parse(subprocess.check_output(["git","show","ae8c75ef39ed26fa505be17e0d8b6152542cbf36:tests/test_workout_footnote_spacing689.py"], text=True))'
for script in scripts/tracker-preview689.sh scripts/tracker-release-scoped689.sh; do
  git show "$TARGET:$script" | bash -n
done
echo "RELEASE_689_SYNTAX_PREFLIGHT=PASSED"
STAGE="$(mktemp -d /tmp/tracker-689-detached.XXXXXXXX)"
chmod 700 "$STAGE"
WORKER="$STAGE/worker.sh"
git show "$WORKER_SHA:$WORKER_PATH" > "$WORKER"
[[ "$(git hash-object "$WORKER")" == "$(git rev-parse "$WORKER_SHA:$WORKER_PATH")" ]] || {
  rm -rf -- "$STAGE"
  fail "Worker hash mismatch"
}
bash -n "$WORKER"
chmod 700 "$WORKER"
UNIT="tracker-preview689-$(date -u +%Y%m%d%H%M%S)-$$"
echo "RELEASE_689_LAUNCH_UNIT=$UNIT"
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
echo "RELEASE_689_LAUNCH=DETACHED"
echo "RELEASE_689_PREVIEW=STARTED_NOT_YET_QUALIFIED"
echo "RELEASE_689_JOURNAL=journalctl --no-pager -u $UNIT -o cat"
echo "RELEASE_689_STATE=systemctl show $UNIT -p ActiveState -p SubState -p Result -p ExecMainStatus"
echo "RELEASE_689_INSTALLATION=NOT_REQUESTED"
