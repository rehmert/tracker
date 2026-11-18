#!/usr/bin/env bash
# Launch isolated Release 687 preview in a detached, bounded systemd service.
# This launcher only stages the verified worker and starts a transient unit.
# No browser tests run in the caller's SSH session.
set -Eeuo pipefail
umask 077
APP=/opt/tracker
OPS_REF=ops/687-ssh-disconnect-investigation
WORKER_PATH=scripts/tracker-preview687-detached-worker.sh
EXPECTED_WORKER_SHA=0a9ae720f20a3a0ab6ddf2bbfd5120eb7aae462f
[[ "$(id -u)" -eq 0 && "$(hostname -s)" == tracker-dev ]] || {
  echo "RELEASE_687_LAUNCH_ERROR=Only root on tracker-dev" >&2; exit 1;
}
cd "$APP"
export GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=safe.directory GIT_CONFIG_VALUE_0="$APP"
[[ "$(git branch --show-current)" == main && -z "$(git status --porcelain)" ]] || {
  echo "RELEASE_687_LAUNCH_ERROR=Require clean DEV main checkout" >&2; exit 1;
}
[[ "$(git rev-parse HEAD)" == 6d6505403ec191df66977ea0fab9d1004f7a022f ]] || {
  echo "RELEASE_687_LAUNCH_ERROR=Require DEV release 686 baseline" >&2; exit 1;
}
systemctl is-active --quiet tracker || {
  echo "RELEASE_687_LAUNCH_ERROR=Tracker service not active" >&2; exit 1;
}
git fetch origin "refs/heads/$OPS_REF:refs/remotes/origin/$OPS_REF"
[[ "$(git rev-parse refs/remotes/origin/$OPS_REF)" == "$EXPECTED_WORKER_SHA" ]] || {
  echo "RELEASE_687_LAUNCH_ERROR=Ops branch moved" >&2; exit 1;
}
STAGE="$(mktemp -d /tmp/tracker-687-detached.XXXXXXXX)"
chmod 700 "$STAGE"
WORKER="$STAGE/worker.sh"
git show "$EXPECTED_WORKER_SHA:$WORKER_PATH" > "$WORKER"
[[ "$(git hash-object "$WORKER")" == "$(git rev-parse "$EXPECTED_WORKER_SHA:$WORKER_PATH")" ]] || {
  rm -rf -- "$STAGE"; echo "RELEASE_687_LAUNCH_ERROR=Worker mismatch" >&2; exit 1;
}
bash -n "$WORKER"
chmod 700 "$WORKER"
UNIT="tracker-preview687-$(date -u +%Y%m%d%H%M%S)-$$"
echo "RELEASE_687_LAUNCH_UNIT=$UNIT"
if ! systemd-run --no-block --collect --unit="$UNIT" \
  --property=MemoryAccounting=yes \
  --property=MemoryMax=2G \
  --property=TasksMax=96 \
  --property=CPUQuota=200% \
  --property=RuntimeMaxSec=900 \
  --property=TimeoutStopSec=15 \
  -- /usr/bin/bash "$WORKER"; then
  rm -rf -- "$STAGE"
  echo "RELEASE_687_LAUNCH=FAILED" >&2
  exit 1
fi
echo "RELEASE_687_LAUNCH=DETACHED"
echo "RELEASE_687_PREVIEW=RUNNING_OR_QUEUED_NOT_YET_QUALIFIED"
echo "RELEASE_687_LOG_COMMAND=journalctl --no-pager -u $UNIT -o cat"
echo "RELEASE_687_STATUS_COMMAND=systemctl status $UNIT --no-pager"
echo "RELEASE_687_STAGING=$STAGE"
echo "RELEASE_687_INSTALLATION=NOT_REQUESTED"
