#!/usr/bin/env bash
set -Eeuo pipefail
umask 077
APP=/opt/tracker
TARGET=696fe7f482436090df5342f76cd65b9fb5febad4
REF=release/692-remove-workout-qr-camera
fail(){ echo "RELEASE_692_PREVIEW_WORKER_ERROR=$*" >&2; exit 1; }
[[ "$(id -u)" == 0 && "$(hostname -s)" == tracker-dev && -n "${INVOCATION_ID:-}" ]] || fail "Detached root on tracker-dev required"
cd "$APP"
export GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=safe.directory GIT_CONFIG_VALUE_0="$APP"
git fetch origin "refs/heads/$REF:refs/remotes/origin/$REF"
[[ "$(git rev-parse "refs/remotes/origin/$REF")" == "$TARGET" ]] || fail "Candidate branch moved"
SCRIPT="$(mktemp /tmp/tracker-692-preview.XXXXXXXX.sh)"
trap 'rm -f "$SCRIPT"' EXIT
git show "$TARGET:scripts/tracker-preview692.sh" > "$SCRIPT"
[[ "$(git hash-object "$SCRIPT")" == "$(git rev-parse "$TARGET:scripts/tracker-preview692.sh")" ]] || fail "Preview script hash mismatch"
bash -n "$SCRIPT"
bash "$SCRIPT"
echo "RELEASE_692_DETACHED_PREVIEW=PASSED"
