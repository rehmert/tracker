#!/usr/bin/env bash
# Start an exact-SHA isolated preview; never installs Release 694.
set -Eeuo pipefail
umask 077
APP=/opt/tracker
BASE=4d752be1a62ffa8a5feba78a50033e980a30b26c
TARGET=d0cba8c10a88c1a78b4d79a9f2d033d579b9ae5d
OPS=ops/694-everyday-navigation-preview
REF=release/694-everyday-navigation
WORKER_SHA=527fc616dd771a987a427bcbf5e51bc0a8364785
WORKER_PATH=scripts/tracker-preview694-detached-worker.sh
fail(){ echo "RELEASE_694_PREVIEW_LAUNCH_ERROR=$*" >&2; exit 1; }
[[ "$(id -u)" == 0 && "$(hostname -s)" == tracker-dev ]] ||
  fail "Root on tracker-dev required"
cd "$APP"
export GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=safe.directory GIT_CONFIG_VALUE_0="$APP"
[[ "$(git branch --show-current)" == main && -z "$(git status --porcelain)" ]] ||
  fail "Require clean DEV main"
[[ "$(git rev-parse HEAD)" == "$BASE" ]] ||
  fail "DEV must be installed Release 693"
systemctl is-active --quiet tracker || fail "DEV Tracker service inactive"
git fetch origin \
  "refs/heads/$OPS:refs/remotes/origin/$OPS" \
  "refs/heads/$REF:refs/remotes/origin/$REF"
git merge-base --is-ancestor "$WORKER_SHA" "refs/remotes/origin/$OPS" ||
  fail "Pinned preview worker absent from ops branch"
[[ "$(git rev-parse "refs/remotes/origin/$REF")" == "$TARGET" ]] ||
  fail "Reviewed Release 694 candidate changed"
git merge-base --is-ancestor "$BASE" "$TARGET" ||
  fail "Candidate ancestry invalid"
STAGE="$(mktemp -d /tmp/tracker-694-launch.XXXXXXXX)"
chmod 700 "$STAGE"
WORKER="$STAGE/worker.sh"
git show "$WORKER_SHA:$WORKER_PATH" > "$WORKER"
if [[ "$(git hash-object "$WORKER")" != "$(git rev-parse "$WORKER_SHA:$WORKER_PATH")" ]]; then
  rm -rf -- "$STAGE"
  fail "Staged worker Git blob mismatch"
fi
bash -n "$WORKER"
chmod 700 "$WORKER"
UNIT="tracker-preview694-$(date -u +%Y%m%d%H%M%S)-$$"
echo "RELEASE_694_PREVIEW_UNIT=$UNIT"
if ! systemd-run --no-block --unit="$UNIT" \
  --property=MemoryAccounting=yes \
  --property=MemoryMax=2G \
  --property=TasksMax=96 \
  --property=CPUQuota=200% \
  --property=RuntimeMaxSec=1800 \
  -- /usr/bin/bash "$WORKER"; then
  rm -rf -- "$STAGE"
  fail "Detached preview launch failed"
fi
echo "RELEASE_694_PREVIEW=STARTED_NOT_QUALIFIED"
echo "RELEASE_694_JOURNAL=journalctl --no-pager -u $UNIT -o cat"
echo "RELEASE_694_STATE=systemctl show $UNIT -p ActiveState -p SubState -p Result -p ExecMainStatus"
echo "RELEASE_694_INSTALLATION=NOT_REQUESTED"
