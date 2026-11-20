#!/usr/bin/env bash
# DEV-controlled Release 710 installation through standard Tracker deployer.
# Source is a pinned GitHub code commit, never downloaded packages or data.
set -Eeuo pipefail
umask 077
APP=/opt/tracker
BASE=4c084ade9063b3b01c2de0a4a055d2e23470b2a3
REF=release/710-unified-blend-vial-dosing
fail() { echo "RELEASE_710_INSTALL_BLOCKED=$*" >&2; exit 1; }
[[ $# == 1 && "$1" =~ ^[0-9a-f]{40}$ ]] || fail "Supply qualified 40-character SHA"
TARGET="$1"
[[ "$(id -u)" == 0 && "$(hostname -s)" == tracker-dev ]] ||
  fail "Must run as root on tracker-dev"
[[ -f /etc/tracker.env && -x "$APP/.venv/bin/python" ]] ||
  fail "Configured Tracker installation unavailable"
cd "$APP"
export GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=safe.directory
export GIT_CONFIG_VALUE_0="$APP"
[[ "$(git branch --show-current)" == main &&
   "$(git rev-parse HEAD)" == "$BASE" &&
   -z "$(git status --porcelain)" ]] ||
  fail "Unexpected installed DEV source or dirty checkout"
systemctl is-active --quiet tracker || fail "Tracker service inactive"
git fetch origin "refs/heads/$REF:refs/remotes/origin/$REF"
[[ "$(git rev-parse "refs/remotes/origin/$REF")" == "$TARGET" ]] ||
  fail "Qualified branch SHA changed"
git merge-base --is-ancestor "$BASE" "$TARGET" ||
  fail "Candidate must be fast-forward"
STAGE="$(mktemp -d /tmp/tracker710-install.XXXXXXXX)"
trap 'rm -rf -- "$STAGE"' EXIT
RUNNER="$STAGE/runner.sh"
git show "$TARGET:scripts/tracker-release.sh" > "$RUNNER"
EXPECTED_BLOB="$(git rev-parse "$TARGET:scripts/tracker-release.sh")"
ACTUAL_BLOB="$(git hash-object "$RUNNER")"
[[ "$ACTUAL_BLOB" == "$EXPECTED_BLOB" ]] ||
  fail "Deployment runner Git blob verification failed"
bash -n "$RUNNER"
echo "RELEASE_710_REVIEWED_TARGET=$TARGET"
echo "=== GUARDED DEV INSTALL, VERIFIED BACKUP, MIGRATION AND RUNTIME ==="
bash "$RUNNER" --instance DEV --base "$BASE" --target "$TARGET" \
  --ref "$REF" --db-migration --reviewed-blend-710
echo "RELEASE_710_DEV_INSTALL=SUCCESS"
