#!/usr/bin/env bash
# Release 691: detached-only isolated migration and COA document preview.
set -Eeuo pipefail
umask 077
APP=/opt/tracker
REF=release/691-coa-document-identifiers
TARGET=6bdddbe0978dd8b22b57ea3b7c1a0d37f9c03ca5
[[ "$(id -u)" -eq 0 && "$(hostname -s)" == tracker-dev ]] || {
  echo "RELEASE_691_WORKER_ERROR=Wrong host or user" >&2
  exit 2
}
[[ -n "$(printenv INVOCATION_ID || true)" ]] || {
  echo "RELEASE_691_WORKER_ERROR=Foreground execution refused" >&2
  exit 2
}
cd "$APP"
export GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=safe.directory GIT_CONFIG_VALUE_0="$APP"
git fetch origin "refs/heads/$REF:refs/remotes/origin/$REF"
[[ "$(git rev-parse "refs/remotes/origin/$REF")" == "$TARGET" ]] || {
  echo "RELEASE_691_WORKER_ERROR=Candidate ref moved" >&2
  exit 1
}
STAGE="$(mktemp /tmp/tracker-691-preview-worker.XXXXXXXX.sh)"
trap 'rm -f "$STAGE"' EXIT
git show "$TARGET:scripts/tracker-preview691.sh" > "$STAGE"
bash -n "$STAGE"
echo "RELEASE_691_DETACHED_START=$(date -u +%FT%TZ)"
bash "$STAGE"
echo "RELEASE_691_DETACHED_SUCCESS=$(date -u +%FT%TZ)"
