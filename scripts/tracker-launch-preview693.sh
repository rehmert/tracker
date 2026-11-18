#!/usr/bin/env bash
# Start isolated Release 693 preview asynchronously. DEV/PROD never modified.
set -Eeuo pipefail
umask 077
APP=/opt/tracker
BASE=696fe7f482436090df5342f76cd65b9fb5febad4
TARGET=cac841fa38287532705ae60624d011b81df63dee
OPS=ops/693-qr-retirement-preview
REF=release/693-retire-workout-qr-mapping-ui
WORKER_SHA=ffa50aad9ab88a4ae057a686997f21ad1e917107
WORKER_PATH=scripts/tracker-preview693-detached-worker.sh
fail(){ echo "RELEASE_693_PREVIEW_LAUNCH_ERROR=$*" >&2; exit 1; }
[[ "$(id -u)" == 0 && "$(hostname -s)" == tracker-dev ]] ||
  fail "Root on tracker-dev required"
cd "$APP"
export GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=safe.directory GIT_CONFIG_VALUE_0="$APP"
[[ "$(git branch --show-current)" == main && -z "$(git status --porcelain)" ]] ||
  fail "DEV must be clean main"
[[ "$(git rev-parse HEAD)" == "$BASE" ]] ||
  fail "DEV must be installed Release 692"
systemctl is-active --quiet tracker || fail "DEV Tracker service inactive"
git fetch origin \
  "refs/heads/$OPS:refs/remotes/origin/$OPS" \
  "refs/heads/$REF:refs/remotes/origin/$REF"
git merge-base --is-ancestor "$WORKER_SHA" "refs/remotes/origin/$OPS" ||
  fail "Approved pinned worker absent"
[[ "$(git rev-parse "refs/remotes/origin/$REF")" == "$TARGET" ]] ||
  fail "Release 693 candidate has changed"
git merge-base --is-ancestor "$BASE" "$TARGET" ||
  fail "Candidate ancestry invalid"
STAGE="$(mktemp -d /tmp/tracker-693-launch.XXXXXXXX)"
chmod 700 "$STAGE"
WORKER="$STAGE/worker.sh"
git show "$WORKER_SHA:$WORKER_PATH" > "$WORKER"
if [[ "$(git hash-object "$WORKER")" != "$(git rev-parse "$WORKER_SHA:$WORKER_PATH")" ]]; then
  rm -rf -- "$STAGE"
  fail "Staged worker Git object mismatch"
fi
bash -n "$WORKER"
chmod 700 "$WORKER"
UNIT="tracker-preview693-$(date -u +%Y%m%d%H%M%S)-$$"
echo "RELEASE_693_PREVIEW_UNIT=$UNIT"
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
echo "RELEASE_693_PREVIEW=STARTED_NOT_QUALIFIED"
echo "RELEASE_693_JOURNAL=journalctl --no-pager -u $UNIT -o cat"
echo "RELEASE_693_STATE=systemctl show $UNIT -p ActiveState -p SubState -p Result -p ExecMainStatus"
echo "RELEASE_693_INSTALLATION=NOT_REQUESTED"
