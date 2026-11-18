#!/usr/bin/env bash
# Detached, bounded Release 687 preview worker.
# ONLY run inside a dedicated systemd transient service. No installation.
set -Eeuo pipefail
umask 077
APP=/opt/tracker
REF=release/687-shortcuts-toolbar
TARGET=6c47f765e76d4e4609f1d36c06226f439b28334d
[[ "$(id -u)" -eq 0 && "$(hostname -s)" == tracker-dev ]] || exit 2
[[ -n "${INVOCATION_ID:-}" ]] || {
  echo "REFUSING_FOREGROUND_EXECUTION=requires_systemd_service" >&2
  exit 2
}
cd "$APP"
export GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=safe.directory GIT_CONFIG_VALUE_0="$APP"
git fetch origin "refs/heads/$REF:refs/remotes/origin/$REF"
[[ "$(git rev-parse refs/remotes/origin/$REF)" == "$TARGET" ]] || {
  echo "PREVIEW_REF_MISMATCH=YES" >&2; exit 1;
}
STAGE="$(mktemp /tmp/tracker-687-bounded.XXXXXXXX.sh)"
trap 'rm -f "$STAGE"' EXIT
git show "$TARGET:scripts/tracker-preview687.sh" > "$STAGE"
bash -n "$STAGE"
echo "PREVIEW_687_DETACHED_START=$(date -u +%FT%TZ)"
bash "$STAGE"
echo "PREVIEW_687_DETACHED_SUCCESS=$(date -u +%FT%TZ)"
