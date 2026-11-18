#!/usr/bin/env bash
# Launch exact verified Release 692 DEV-controlled PROD rollout as systemd worker.
set -Eeuo pipefail
umask 077
APP=/opt/tracker
BASE=869ada02eb9ac523ca9e8ce7c19ed6b92b303d68
TARGET=696fe7f482436090df5342f76cd65b9fb5febad4
OPS=ops/692-full-rollout
REF=release/692-remove-workout-qr-camera
WORKER_SHA=0802bdc60fcc69721b00300be11353d475dde0aa
WORKER_PATH=scripts/tracker-rollout692-worker.sh
fail(){ echo "RELEASE_692_LAUNCH_ERROR=$*" >&2; exit 1; }
[[ "$(id -u)" == 0 && "$(hostname -s)" == tracker-dev ]] ||
  fail "Root on tracker-dev required"
cd "$APP"
export GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=safe.directory GIT_CONFIG_VALUE_0="$APP"
[[ "$(git branch --show-current)" == main && -z "$(git status --porcelain)" ]] ||
  fail "Require clean DEV main"
DEV_HEAD="$(git rev-parse HEAD)"
[[ "$DEV_HEAD" == "$BASE" || "$DEV_HEAD" == "$TARGET" ]] ||
  fail "DEV not on expected Release 691 or 692"
systemctl is-active --quiet tracker || fail "Tracker service inactive"
git fetch origin main \
  "refs/heads/$OPS:refs/remotes/origin/$OPS" \
  "refs/heads/$REF:refs/remotes/origin/$REF"
[[ "$(git rev-parse origin/main)" == "$BASE" || "$(git rev-parse origin/main)" == "$TARGET" ]] ||
  fail "GitHub main unexpected"
[[ "$(git rev-parse "refs/remotes/origin/$REF")" == "$TARGET" ]] ||
  fail "Qualified release ref changed"
git merge-base --is-ancestor "$WORKER_SHA" "refs/remotes/origin/$OPS" ||
  fail "Pinned rollout worker missing from approved operations branch"
git merge-base --is-ancestor "$BASE" "$TARGET" || fail "Candidate ancestry invalid"
STAGE="$(mktemp -d /tmp/tracker-692-full-launch.XXXXXXXX)"
chmod 700 "$STAGE"
WORKER="$STAGE/worker.sh"
git show "$WORKER_SHA:$WORKER_PATH" > "$WORKER"
if [[ "$(git hash-object "$WORKER")" != "$(git rev-parse "$WORKER_SHA:$WORKER_PATH")" ]]; then
  rm -rf -- "$STAGE"
  fail "Staged worker blob differs from pin"
fi
bash -n "$WORKER"
chmod 700 "$WORKER"
UNIT="tracker-full692-$(date -u +%Y%m%d%H%M%S)-$$"
echo "RELEASE_692_FULL_ROLLOUT_UNIT=$UNIT"
if ! systemd-run --no-block --unit="$UNIT" \
  --property=MemoryAccounting=yes \
  --property=MemoryMax=2G \
  --property=TasksMax=128 \
  --property=CPUQuota=300% \
  --property=RuntimeMaxSec=3600 \
  --property=TimeoutStopSec=30 \
  -- /usr/bin/bash "$WORKER"; then
  rm -rf -- "$STAGE"
  fail "Detached rollout launch failed"
fi
echo "RELEASE_692_FULL_ROLLOUT=STARTED_NOT_YET_VERIFIED"
echo "RELEASE_692_ROLLOUT_JOURNAL=journalctl --no-pager -u $UNIT -o cat"
echo "RELEASE_692_ROLLOUT_STATE=systemctl show $UNIT -p ActiveState -p SubState -p Result -p ExecMainStatus"
echo "RELEASE_692_INSTALLATION=DEV_THEN_SIGNED_PROD_PENDING"
