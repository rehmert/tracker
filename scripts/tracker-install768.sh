#!/usr/bin/env bash
# Release 768 guarded DEV install. Invoked only after immutable passed qualification.
set -Eeuo pipefail
umask 077
APP=/opt/tracker
BASE=5d23aaf4f7e7fa4b54c1d5535a622bdd9e9aac13
REF=release/768-prod-relative-data-path-recovery
fail(){ echo "RELEASE_768_INSTALL_BLOCKED=$*" >&2; exit 1; }
[[ $# == 1 && "$1" =~ ^[0-9a-f]{40}$ ]] || fail "Exact pinned SHA required"
TARGET="$1"
[[ "$(id -u)" == 0 && "$(hostname -s)" == tracker-dev ]] || fail "DEV only"
[[ -f /etc/tracker.env && -x "$APP/.venv/bin/python" ]] || fail "DEV missing"
cd "$APP"
export GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=safe.directory
export GIT_CONFIG_VALUE_0="$APP"
[[ "$(git branch --show-current)" == main &&
 "$(git rev-parse HEAD)" == "$BASE" && -z "$(git status --porcelain)" ]] ||
 fail "Unexpected DEV Release 767 installed baseline"
systemctl is-active --quiet tracker.service || fail "DEV service inactive"
# Manual bootstrapping is required because the already-installed 745 controller
# refuses a failed production stage; fail rather than silently bypass it.
AGENT=/usr/local/sbin/tracker-release-agent.py
[[ -f "$AGENT" && ! -L "$AGENT" &&
   "$(stat -c '%u:%a' "$AGENT")" == 0:700 &&
   "$(git hash-object "$AGENT")" ==
   "$(git rev-parse "$TARGET:scripts/tracker-release-agent745.py")" ]] ||
  fail "Signed Release 768 host recovery agent not bootstrapped"
git fetch origin "refs/heads/$REF:refs/remotes/origin/$REF"
[[ "$(git rev-parse "refs/remotes/origin/$REF")" == "$TARGET" ]] ||
 fail "Release branch moved"
git merge-base --is-ancestor "$BASE" "$TARGET" || fail "Not a descendant of DEV base"
[[ -z "$(git diff --name-only "$BASE" "$TARGET" -- \
  app/models.py app/migrations.py app/db.py app/progress_models762.py)" ]] || \
 fail "Release 768 is code-only; schema change not permitted"
STAGE="$(mktemp -d /tmp/tracker768-install.XXXXXXXX)"
trap 'rm -rf -- "$STAGE"' EXIT
RUNNER="$STAGE/runner.sh"
git show "$TARGET:scripts/tracker-release.sh" > "$RUNNER"
[[ "$(git hash-object "$RUNNER")" == "$(git rev-parse "$TARGET:scripts/tracker-release.sh")" ]] ||
 fail "Pinned release runner integrity mismatch"
bash -n "$RUNNER"
echo "RELEASE_768_PINNED_TARGET=$TARGET"
bash "$RUNNER" --instance DEV --base "$BASE" --target "$TARGET" --ref "$REF"
[[ "$(git branch --show-current)" == main &&
 "$(git rev-parse HEAD)" == "$TARGET" &&
 -z "$(git status --porcelain)" ]] || fail "Installed DEV commit mismatch"
systemctl is-active --quiet tracker.service || fail "DEV service not active after install"
echo "RELEASE_768_DEV_INSTALL=SUCCESS"
