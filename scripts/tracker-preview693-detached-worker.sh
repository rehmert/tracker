#!/usr/bin/env bash
# Detached Release 693 isolated qualification worker; never installs.
set -Eeuo pipefail
umask 077
APP=/opt/tracker
REF=release/693-retire-workout-qr-mapping-ui
TARGET=cac841fa38287532705ae60624d011b81df63dee
fail(){ echo "RELEASE_693_DETACHED_PREVIEW_ERROR=$*" >&2; exit 1; }
[[ "$(id -u)" == 0 && "$(hostname -s)" == tracker-dev &&
   -n "$(printenv INVOCATION_ID || true)" ]] ||
  fail "Only detached root systemd worker on tracker-dev"
cd "$APP"
export GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=safe.directory GIT_CONFIG_VALUE_0="$APP"
git fetch origin "refs/heads/$REF:refs/remotes/origin/$REF"
[[ "$(git rev-parse "refs/remotes/origin/$REF")" == "$TARGET" ]] ||
  fail "Qualified source ref changed"
STAGE="$(mktemp /tmp/tracker-693-preview.XXXXXXXX.sh)"
trap 'rm -f -- "$STAGE"' EXIT
git show "$TARGET:scripts/tracker-preview693.sh" > "$STAGE"
[[ "$(git hash-object "$STAGE")" == "$(git rev-parse "$TARGET:scripts/tracker-preview693.sh")" ]] ||
  fail "Detached preview runner not equal to pinned Git object"
bash -n "$STAGE"
bash "$STAGE"
echo "RELEASE_693_DETACHED_PREVIEW=PASSED"
