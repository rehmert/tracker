#!/usr/bin/env bash
# Release 742 guarded source-only security, dependency, release-chain and UX DEV install; exact qualified SHA only.
set -Eeuo pipefail
umask 077
APP=/opt/tracker
BASE=c5efed6b40f4324187eff3e83dbed44d9e68f5c4
REF=release/742-security-deps-controller-ux
fail() { echo "RELEASE_742_INSTALL_BLOCKED=$*" >&2; exit 1; }
[[ $# == 1 && "$1" =~ ^[0-9a-f]{40}$ ]] ||
  fail "Supply qualified exact commit SHA"
TARGET="$1"
[[ "$(id -u)" == 0 && "$(hostname -s)" == tracker-dev ]] ||
  fail "Must run as root on tracker-dev"
[[ -f /etc/tracker.env && -x "$APP/.venv/bin/python" ]] ||
  fail "Tracker environment unavailable"
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
git merge-base --is-ancestor "$BASE" "$TARGET" ||
  fail "Candidate not fast-forward"
STAGE="$(mktemp -d /tmp/tracker742-install.XXXXXXXX)"
trap 'rm -rf -- "$STAGE"' EXIT
RUNNER="$STAGE/runner.sh"
git show "$TARGET:scripts/tracker-release.sh" > "$RUNNER"
EXPECTED_BLOB="$(git rev-parse "$TARGET:scripts/tracker-release.sh")"
ACTUAL_BLOB="$(git hash-object "$RUNNER")"
[[ "$ACTUAL_BLOB" == "$EXPECTED_BLOB" ]] ||
  fail "Runner Git blob mismatch"
bash -n "$RUNNER"
echo "RELEASE_742_PINNED_TARGET=$TARGET"
bash "$RUNNER" --instance DEV --base "$BASE" --target "$TARGET" --ref "$REF"
echo "RELEASE_742_DEV_INSTALL=SUCCESS"
