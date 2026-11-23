#!/usr/bin/env bash
# Release 758 guarded DEV install. Invoked only after immutable passed qualification.
set -Eeuo pipefail
umask 077
APP=/opt/tracker
BASE=90b297fc07c950d5a44a0bf8fe7d4beabfd8b30f
REF=release/758-vial-label-dose-markings
fail(){ echo "RELEASE_758_INSTALL_BLOCKED=$*" >&2; exit 1; }
[[ $# == 1 && "$1" =~ ^[0-9a-f]{40}$ ]] || fail "Exact pinned SHA required"
TARGET="$1"
[[ "$(id -u)" == 0 && "$(hostname -s)" == tracker-dev ]] || fail "DEV only"
[[ -f /etc/tracker.env && -x "$APP/.venv/bin/python" ]] || fail "DEV missing"
cd "$APP"
export GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=safe.directory
export GIT_CONFIG_VALUE_0="$APP"
[[ "$(git branch --show-current)" == main &&
 "$(git rev-parse HEAD)" == "$BASE" && -z "$(git status --porcelain)" ]] ||
 fail "Unexpected DEV installed baseline"
systemctl is-active --quiet tracker.service || fail "DEV service inactive"
git fetch origin "refs/heads/$REF:refs/remotes/origin/$REF"
[[ "$(git rev-parse "refs/remotes/origin/$REF")" == "$TARGET" ]] ||
 fail "Release branch moved"
git merge-base --is-ancestor "$BASE" "$TARGET" || fail "Not a descendant of DEV base"
STAGE="$(mktemp -d /tmp/tracker758-install.XXXXXXXX)"
trap 'rm -rf -- "$STAGE"' EXIT
RUNNER="$STAGE/runner.sh"
git show "$TARGET:scripts/tracker-release.sh" > "$RUNNER"
[[ "$(git hash-object "$RUNNER")" == "$(git rev-parse "$TARGET:scripts/tracker-release.sh")" ]] ||
 fail "Pinned release runner integrity mismatch"
bash -n "$RUNNER"
echo "RELEASE_758_PINNED_TARGET=$TARGET"
bash "$RUNNER" --instance DEV --base "$BASE" --target "$TARGET" --ref "$REF"
[[ "$(git branch --show-current)" == main &&
 "$(git rev-parse HEAD)" == "$TARGET" &&
 -z "$(git status --porcelain)" ]] || fail "Installed DEV commit mismatch"
systemctl is-active --quiet tracker.service || fail "DEV service not active after install"
echo "RELEASE_758_DEV_INSTALL=SUCCESS"
