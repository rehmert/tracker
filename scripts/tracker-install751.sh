#!/usr/bin/env bash
# Release 751: full regression before live DEV-only CSRF flag activation.
set -Eeuo pipefail
umask 077
APP=/opt/tracker
BASE=2ff72f49449306ea5b11dc9c861d0cac5973131e
REF=release/751-strict-csrf-dev-rollout
die(){ echo "RELEASE_751_INSTALL_BLOCKED=$*" >&2; exit 1; }
[[ $# == 1 && "$1" =~ ^[0-9a-f]{40}$ ]] || die "Exact target required"
TARGET="$1"
[[ "$(id -u)" == 0 && "$(hostname -s)" == tracker-dev ]] || die "DEV only"
[[ -x "$APP/.venv/bin/python" && -f /etc/tracker.env ]] || die "DEV missing"
cd "$APP"
export GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=safe.directory
export GIT_CONFIG_VALUE_0="$APP"
[[ "$(git branch --show-current)" == main &&
 "$(git rev-parse HEAD)" == "$BASE" && -z "$(git status --porcelain)" ]] ||
 die "Unexpected DEV state"
systemctl is-active --quiet tracker.service || die "DEV service inactive"
git fetch origin "refs/heads/$REF:refs/remotes/origin/$REF"
[[ "$(git rev-parse "refs/remotes/origin/$REF")" == "$TARGET" ]] ||
 die "Release branch moved"
git merge-base --is-ancestor "$BASE" "$TARGET" || die "Not fast forward"
STAGE="$(mktemp -d /tmp/tracker751-install.XXXXXXXX)"
trap 'rm -rf -- "$STAGE"' EXIT
RUNNER="$STAGE/runner.sh"
git show "$TARGET:scripts/tracker-release.sh" > "$RUNNER"
[[ "$(git hash-object "$RUNNER")" == \
 "$(git rev-parse "$TARGET:scripts/tracker-release.sh")" ]] ||
 die "Pinned release runner mismatch"
bash -n "$RUNNER"
echo "RELEASE_751_PINNED_TARGET=$TARGET"
echo "RELEASE_751_FULL_QA=REQUIRED"
bash "$RUNNER" --instance DEV --base "$BASE" --target "$TARGET" --ref "$REF" --full-suite
[[ "$(git rev-parse HEAD)" == "$TARGET" && -z "$(git status --porcelain)" ]] ||
 die "Full QA finished but DEV commit mismatched"
echo "RELEASE_751_FULL_QA_INSTALL=PASSED"
bash "$APP/scripts/tracker-csrf-dev751.sh" enable "$TARGET"
bash "$APP/scripts/tracker-csrf-dev751.sh" status
echo "RELEASE_751_DEV_STRICT_CSRF_ACTIVATION=PASSED"
echo "RELEASE_751_DEV_INSTALL=SUCCESS"
