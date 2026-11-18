#!/usr/bin/env bash
# Release 689: run isolated preview only in detached systemd.
set -Eeuo pipefail
umask 077
APP=/opt/tracker
REF=release/689-workout-footnote-spacing
TARGET=ae8c75ef39ed26fa505be17e0d8b6152542cbf36
[[ "$(id -u)" -eq 0 && "$(hostname -s)" == tracker-dev ]] || {
  echo "RELEASE_689_WORKER_ERROR=Wrong host or user" >&2
  exit 2
}
[[ -n "${INVOCATION_ID:-}" ]] || {
  echo "RELEASE_689_WORKER_ERROR=Foreground execution refused" >&2
  exit 2
}
cd "$APP"
export GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=safe.directory GIT_CONFIG_VALUE_0="$APP"
git fetch origin "refs/heads/$REF:refs/remotes/origin/$REF"
[[ "$(git rev-parse "refs/remotes/origin/$REF")" == "$TARGET" ]] || {
  echo "RELEASE_689_WORKER_ERROR=Candidate ref changed" >&2
  exit 1
}
STAGE="$(mktemp /tmp/tracker-689-preview-worker.XXXXXXXX.sh)"
trap 'rm -f "$STAGE"' EXIT
git show "$TARGET:scripts/tracker-preview689.sh" > "$STAGE"
bash -n "$STAGE"
echo "RELEASE_689_DETACHED_START=$(date -u +%FT%TZ)"
bash "$STAGE"
echo "RELEASE_689_DETACHED_SUCCESS=$(date -u +%FT%TZ)"
