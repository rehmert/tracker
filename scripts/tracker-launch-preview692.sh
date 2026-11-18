#!/usr/bin/env bash
set -Eeuo pipefail
umask 077
APP=/opt/tracker
BASE=869ada02eb9ac523ca9e8ce7c19ed6b92b303d68
TARGET=696fe7f482436090df5342f76cd65b9fb5febad4
OPS=ops/692-scanner-removal-preview
REF=release/692-remove-workout-qr-camera
WORKER_SHA=9276db917400899f1fb194e2ed90c3c6fa2fb612
PATH_IN_REPO=scripts/tracker-preview692-detached-worker.sh
fail(){ echo "RELEASE_692_PREVIEW_LAUNCH_ERROR=$*" >&2; exit 1; }
[[ "$(id -u)" == 0 && "$(hostname -s)" == tracker-dev ]] || fail "Root on tracker-dev required"
cd "$APP"
export GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=safe.directory GIT_CONFIG_VALUE_0="$APP"
[[ "$(git branch --show-current)" == main && -z "$(git status --porcelain)" ]] || fail "DEV checkout is not clean main"
[[ "$(git rev-parse HEAD)" == "$BASE" ]] || fail "DEV must be on installed Release 691"
systemctl is-active --quiet tracker || fail "Tracker service inactive"
git fetch origin "refs/heads/$OPS:refs/remotes/origin/$OPS" "refs/heads/$REF:refs/remotes/origin/$REF"
git merge-base --is-ancestor "$WORKER_SHA" "refs/remotes/origin/$OPS" || fail "Pinned worker missing"
[[ "$(git rev-parse "refs/remotes/origin/$REF")" == "$TARGET" ]] || fail "Release ref differs from pin"
git merge-base --is-ancestor "$BASE" "$TARGET" || fail "Candidate ancestry invalid"
STAGE="$(mktemp -d /tmp/tracker-692-detached.XXXXXXXX)"
chmod 700 "$STAGE"
WORKER="$STAGE/worker.sh"
git show "$WORKER_SHA:$PATH_IN_REPO" > "$WORKER"
[[ "$(git hash-object "$WORKER")" == "$(git rev-parse "$WORKER_SHA:$PATH_IN_REPO")" ]] || { rm -rf -- "$STAGE"; fail "Worker hash mismatch"; }
bash -n "$WORKER"
chmod 700 "$WORKER"
UNIT="tracker-preview692-$(date -u +%Y%m%d%H%M%S)-$$"
echo "RELEASE_692_PREVIEW_UNIT=$UNIT"
if ! systemd-run --no-block --unit="$UNIT" --property=MemoryAccounting=yes --property=MemoryMax=2G --property=TasksMax=96 --property=CPUQuota=200% --property=RuntimeMaxSec=1800 -- /usr/bin/bash "$WORKER"; then
 rm -rf -- "$STAGE"
 fail "systemd failed to launch preview"
fi
echo "RELEASE_692_PREVIEW=STARTED_NOT_QUALIFIED"
echo "RELEASE_692_JOURNAL=journalctl --no-pager -u $UNIT -o cat"
echo "RELEASE_692_STATE=systemctl show $UNIT -p ActiveState -p SubState -p Result -p ExecMainStatus"
echo "RELEASE_692_INSTALLATION=NOT_REQUESTED"
