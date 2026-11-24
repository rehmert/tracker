#!/usr/bin/env bash
# Release 767 guarded DEV install. Invoked only after immutable passed qualification.
set -Eeuo pipefail
umask 077
APP=/opt/tracker
BASE=45263b9659232b6ac6a922da38599f92842a32d8
REF=release/767-prod-device-schema-guard
fail(){ echo "RELEASE_767_INSTALL_BLOCKED=$*" >&2; exit 1; }
[[ $# == 1 && "$1" =~ ^[0-9a-f]{40}$ ]] || fail "Exact pinned SHA required"
TARGET="$1"
[[ "$(id -u)" == 0 && "$(hostname -s)" == tracker-dev ]] || fail "DEV only"
[[ -f /etc/tracker.env && -x "$APP/.venv/bin/python" ]] || fail "DEV missing"
cd "$APP"
export GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=safe.directory
export GIT_CONFIG_VALUE_0="$APP"
[[ "$(git branch --show-current)" == main &&
 "$(git rev-parse HEAD)" == "$BASE" && -z "$(git status --porcelain)" ]] ||
 fail "Unexpected DEV Release 766 installed baseline"
systemctl is-active --quiet tracker.service || fail "DEV service inactive"
git fetch origin "refs/heads/$REF:refs/remotes/origin/$REF"
[[ "$(git rev-parse "refs/remotes/origin/$REF")" == "$TARGET" ]] ||
 fail "Release branch moved"
git merge-base --is-ancestor "$BASE" "$TARGET" || fail "Not a descendant of DEV base"
[[ -z "$(git diff --name-only "$BASE" "$TARGET" -- \
  app/models.py app/migrations.py app/db.py app/progress_models762.py)" ]] || \
 fail "Release 767 is code-only; schema change not permitted"
STAGE="$(mktemp -d /tmp/tracker767-install.XXXXXXXX)"
trap 'rm -rf -- "$STAGE"' EXIT
RUNNER="$STAGE/runner.sh"
git show "$TARGET:scripts/tracker-release.sh" > "$RUNNER"
[[ "$(git hash-object "$RUNNER")" == "$(git rev-parse "$TARGET:scripts/tracker-release.sh")" ]] ||
 fail "Pinned release runner integrity mismatch"
bash -n "$RUNNER"
echo "RELEASE_767_PINNED_TARGET=$TARGET"
bash "$RUNNER" --instance DEV --base "$BASE" --target "$TARGET" --ref "$REF"
[[ "$(git branch --show-current)" == main &&
 "$(git rev-parse HEAD)" == "$TARGET" &&
 -z "$(git status --porcelain)" ]] || fail "Installed DEV commit mismatch"
systemctl is-active --quiet tracker.service || fail "DEV service not active after install"
echo "RELEASE_767_DEV_INSTALL=SUCCESS"
