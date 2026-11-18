#!/usr/bin/env bash
# Stage verified GitHub ops files, then install DEV-only upload sync systemd timer.
# No upload transfer runs in this SSH session; the timer/service owns execution.
set -Eeuo pipefail
umask 077
APP=/opt/tracker
OPS=ops/dev-upload-sync-minute
fail() { echo "UPLOAD_SYNC_LAUNCH_ERROR=$*" >&2; exit 1; }
[[ $# == 1 && "$1" =~ ^[0-9a-f]{40}$ ]] || fail "Pinned operations SHA required"
SHA="$1"
[[ "$(id -u)" == 0 && "$(hostname -s)" == tracker-dev ]] ||
  fail "Run as root on tracker-dev"
cd "$APP"
export GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=safe.directory GIT_CONFIG_VALUE_0="$APP"
[[ "$(git branch --show-current)" == main && -z "$(git status --porcelain)" ]] ||
  fail "Require clean DEV application checkout on main"
[[ "$(git rev-parse HEAD)" == ae8c75ef39ed26fa505be17e0d8b6152542cbf36 ]] ||
  fail "Release 689 must be installed on DEV"
[[ "$(git rev-parse "refs/remotes/origin/$OPS")" == "$SHA" ]] ||
  fail "Ops ref not pinned to the audited SHA"
STAGE="$(mktemp -d /tmp/tracker-upload-sync-minute.XXXXXXXX)"
chmod 700 "$STAGE"
trap 'rm -rf -- "$STAGE"' EXIT
for source in \
  deploy/tracker-upload-sync-dev.service \
  deploy/tracker-upload-sync-dev.timer \
  scripts/tracker-install-upload-sync-minute.sh \
  tests/test_upload_sync_minute_ops.py; do
  file="${source##*/}"
  git show "$SHA:$source" > "$STAGE/$file"
  [[ "$(git hash-object "$STAGE/$file")" == "$(git rev-parse "$SHA:$source")" ]] ||
    fail "Staged source hash mismatch: $source"
done
bash -n "$STAGE/tracker-install-upload-sync-minute.sh"
"$APP/.venv/bin/python" -m py_compile "$STAGE/test_upload_sync_minute_ops.py"
echo "UPLOAD_SYNC_LAUNCH_PREFLIGHT=PASSED"
bash "$STAGE/tracker-install-upload-sync-minute.sh" "$STAGE"
echo "UPLOAD_SYNC_SETUP=SUCCESS"
