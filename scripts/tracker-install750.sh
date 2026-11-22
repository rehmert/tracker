#!/usr/bin/env bash
set -Eeuo pipefail
umask 077
APP=/opt/tracker
BASE=e80edbfa5ef5c7d41a953be36c60c4828b4a86d7
REF=release/750-offline-browser-multiuser-acceptance
fail(){ echo "RELEASE_750_INSTALL_BLOCKED=$*" >&2; exit 1; }
[[ $# == 1 && "$1" =~ ^[0-9a-f]{40}$ ]] || fail "Exact SHA required"
TARGET="$1"
[[ "$(id -u)" == 0 && "$(hostname -s)" == tracker-dev ]] || fail "DEV only"
[[ -f /etc/tracker.env && -x "$APP/.venv/bin/python" ]] || fail "DEV missing"
cd "$APP"
export GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=safe.directory
export GIT_CONFIG_VALUE_0="$APP"
[[ "$(git branch --show-current)" == main &&
 "$(git rev-parse HEAD)" == "$BASE" && -z "$(git status --porcelain)" ]] ||
 fail "Unexpected DEV source"
systemctl is-active --quiet tracker || fail "Tracker inactive"
git fetch origin "refs/heads/$REF:refs/remotes/origin/$REF"
[[ "$(git rev-parse "refs/remotes/origin/$REF")" == "$TARGET" ]] ||
 fail "Branch SHA changed"
git merge-base --is-ancestor "$BASE" "$TARGET" || fail "Not fast forward"
STAGE="$(mktemp -d /tmp/tracker750-install.XXXXXXXX)"
trap 'rm -rf -- "$STAGE"' EXIT
RUNNER="$STAGE/runner.sh"
git show "$TARGET:scripts/tracker-release.sh" > "$RUNNER"
[[ "$(git hash-object "$RUNNER")" == \
 "$(git rev-parse "$TARGET:scripts/tracker-release.sh")" ]] || fail "Runner blob mismatch"
bash -n "$RUNNER"
echo "RELEASE_750_PINNED_TARGET=$TARGET"
bash "$RUNNER" --instance DEV --base "$BASE" --target "$TARGET" --ref "$REF"
echo "RELEASE_750_DEV_INSTALL=SUCCESS"
