#!/usr/bin/env bash
# Operator-approved detached, DEV-controlled full Tracker rollout through 691.
set -Eeuo pipefail
umask 077
APP=/opt/tracker
OPS=ops/691-full-rollout
REF691=release/691-coa-document-identifiers
REF690=release/690-overview-card-density
WORKER_SHA=6c3b943ed40ce65c8bce1571402cf55851321046
TARGET=869ada02eb9ac523ca9e8ce7c19ed6b92b303d68
BASE689=ae8c75ef39ed26fa505be17e0d8b6152542cbf36
BASE690=6a8cd357e7e8925228d1a37c50572f93c4ec0943
PROD_BASE=b42b39cb9f490325358a9a7ddc305ac7ca6ed5fb
fail(){ echo "TRACKER_691_LAUNCH_ERROR=$*" >&2; exit 1; }
[[ "$(id -u)" == 0 && "$(hostname -s)" == tracker-dev ]] ||
  fail "Only root on tracker-dev"
cd "$APP"
export GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=safe.directory GIT_CONFIG_VALUE_0="$APP"
[[ "$(git branch --show-current)" == main && -z "$(git status --porcelain)" ]] ||
  fail "Require clean DEV main"
HEAD="$(git rev-parse HEAD)"
[[ "$HEAD" == "$BASE689" || "$HEAD" == "$BASE690" || "$HEAD" == "$TARGET" ]] ||
  fail "DEV is not an expected safe starting release"
systemctl is-active --quiet tracker || fail "DEV Tracker service inactive"
git fetch origin main \
  "refs/heads/$OPS:refs/remotes/origin/$OPS" \
  "refs/heads/$REF690:refs/remotes/origin/$REF690" \
  "refs/heads/$REF691:refs/remotes/origin/$REF691"
[[ "$(git rev-parse origin/main)" == "$PROD_BASE" ||
   "$(git rev-parse origin/main)" == "$TARGET" ]] ||
  fail "GitHub main has an unexpected commit"
[[ "$(git rev-parse "refs/remotes/origin/$REF690")" == "$BASE690" &&
   "$(git rev-parse "refs/remotes/origin/$REF691")" == "$TARGET" ]] ||
  fail "Qualified source refs changed"
git merge-base --is-ancestor "$WORKER_SHA" "refs/remotes/origin/$OPS" ||
  fail "Pinned rollout worker missing from operations branch"
git merge-base --is-ancestor "$BASE689" "$BASE690" ||
  fail "690 not descended from verified 689"
git merge-base --is-ancestor "$BASE690" "$TARGET" ||
  fail "691 not descended from qualified 690"
STAGE="$(mktemp -d /tmp/tracker-691-launch.XXXXXXXX)"
chmod 700 "$STAGE"
WORKER="$STAGE/worker.sh"
git show "$WORKER_SHA:scripts/tracker-rollout691-worker.sh" > "$WORKER"
if [[ "$(git hash-object "$WORKER")" != "$(git rev-parse "$WORKER_SHA:scripts/tracker-rollout691-worker.sh")" ]]; then
  rm -rf -- "$STAGE"
  fail "Rollout worker does not match pinned Git blob"
fi
bash -n "$WORKER"
chmod 700 "$WORKER"
UNIT="tracker-full691-$(date -u +%Y%m%d%H%M%S)-$$"
echo "TRACKER_691_ROLLOUT_UNIT=$UNIT"
if ! systemd-run --no-block --unit="$UNIT" \
  --property=MemoryAccounting=yes \
  --property=MemoryMax=2G \
  --property=TasksMax=128 \
  --property=CPUQuota=300% \
  --property=RuntimeMaxSec=5400 \
  --property=TimeoutStopSec=30 \
  -- /usr/bin/bash "$WORKER"; then
  rm -rf -- "$STAGE"
  fail "Failed to launch detached rollout"
fi
echo "TRACKER_691_ROLLOUT=DETACHED_STARTED_NOT_VERIFIED"
echo "TRACKER_691_ROLLOUT_STAGE=DEV_REQUALIFY_THEN_DEV690_DEV691_THEN_SIGNED_PROD"
echo "TRACKER_691_ROLLOUT_JOURNAL=journalctl --no-pager -u $UNIT -o cat"
echo "TRACKER_691_ROLLOUT_STATE=systemctl show $UNIT -p ActiveState -p SubState -p Result -p ExecMainStatus"
echo "PROD_DEPLOY_VERIFIED=NOT_YET"
