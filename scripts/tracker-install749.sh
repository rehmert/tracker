#!/usr/bin/env bash
# Release 749 guarded DEV install; exact previously qualified SHA only.
set -Eeuo pipefail
umask 077
APP=/opt/tracker
BASE=bd59b6e84ded0e55f91c5d88908ef2a1372ea429
REF=release/749-portrait-sidebar-fit
fail() { echo "RELEASE_749_INSTALL_BLOCKED=$*" >&2; exit 1; }
[[ $# == 1 && "$1" =~ ^[0-9a-f]{40}$ ]] || fail "Exact candidate SHA required"
TARGET="$1"
[[ "$(id -u)" == 0 && "$(hostname -s)" == tracker-dev ]] ||
  fail "Must run as root on tracker-dev"
[[ -f /etc/tracker.env && -x "$APP/.venv/bin/python" ]] ||
  fail "Tracker environment missing"
cd "$APP"
export GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=safe.directory
export GIT_CONFIG_VALUE_0="$APP"
[[ "$(git branch --show-current)" == main &&
   "$(git rev-parse HEAD)" == "$BASE" &&
   -z "$(git status --porcelain)" ]] ||
  fail "Unexpected DEV source or dirty tree"
systemctl is-active --quiet tracker || fail "Tracker service inactive"
git fetch origin "refs/heads/$REF:refs/remotes/origin/$REF"
[[ "$(git rev-parse "refs/remotes/origin/$REF")" == "$TARGET" ]] ||
  fail "Release SHA changed"
git merge-base --is-ancestor "$BASE" "$TARGET" || fail "Not a fast-forward"
STAGE="$(mktemp -d /tmp/tracker749-install.XXXXXXXX)"
trap 'rm -rf -- "$STAGE"' EXIT
RUNNER="$STAGE/runner.sh"
git show "$TARGET:scripts/tracker-release.sh" > "$RUNNER"
[[ "$(git hash-object "$RUNNER")" == \
   "$(git rev-parse "$TARGET:scripts/tracker-release.sh")" ]] ||
  fail "Pinned runner hash mismatch"
bash -n "$RUNNER"
echo "RELEASE_749_PINNED_TARGET=$TARGET"
bash "$RUNNER" --instance DEV --base "$BASE" --target "$TARGET" --ref "$REF"
echo "RELEASE_749_DEV_INSTALL=SUCCESS"
