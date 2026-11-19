#!/usr/bin/env bash
# Detached Release 694 isolated qualification; no DEV/PROD installation.
set -Eeuo pipefail
umask 077
APP=/opt/tracker
REF=release/694-everyday-navigation
TARGET=d0cba8c10a88c1a78b4d79a9f2d033d579b9ae5d
fail(){ echo "RELEASE_694_DETACHED_PREVIEW_ERROR=$*" >&2; exit 1; }
[[ "$(id -u)" == 0 && "$(hostname -s)" == tracker-dev &&
   -n "$(printenv INVOCATION_ID || true)" ]] ||
  fail "Detached systemd root worker on tracker-dev only"
cd "$APP"
export GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=safe.directory GIT_CONFIG_VALUE_0="$APP"
git fetch origin "refs/heads/$REF:refs/remotes/origin/$REF"
[[ "$(git rev-parse "refs/remotes/origin/$REF")" == "$TARGET" ]] ||
  fail "Reviewed release candidate ref moved"
STAGE="$(mktemp /tmp/tracker-694-preview.XXXXXXXX.sh)"
trap 'rm -f -- "$STAGE"' EXIT
git show "$TARGET:scripts/tracker-preview694.sh" > "$STAGE"
[[ "$(git hash-object "$STAGE")" == "$(git rev-parse "$TARGET:scripts/tracker-preview694.sh")" ]] ||
  fail "Staged preview script blob differs from immutable candidate"
bash -n "$STAGE"
bash "$STAGE"
echo "RELEASE_694_DETACHED_PREVIEW=PASSED"
