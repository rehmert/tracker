#!/usr/bin/env bash
# Release 763 DEV-only install; 762 schema already exists on DEV.
# A separately reviewed PROD catch-up must invoke --db-migration.
set -Eeuo pipefail
umask 077
APP=/opt/tracker
BASE=35f6aa42aac648f3ed5af527620bd5f4b702b486
REF=release/763-progress-prod-hardening
fail(){ echo "RELEASE_763_INSTALL_BLOCKED=$*" >&2; exit 1; }
[[ $# == 1 && "$1" =~ ^[0-9a-f]{40}$ ]] || fail "Exact target SHA required"
TARGET="$1"
[[ "$(id -u)" == 0 && "$(hostname -s)" == tracker-dev ]] || fail "DEV only"
[[ -f /etc/tracker.env && -x "$APP/.venv/bin/python" ]] || fail "DEV environment missing"
cd "$APP"
export GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=safe.directory GIT_CONFIG_VALUE_0="$APP"
[[ "$(git branch --show-current)" == main &&
   "$(git rev-parse HEAD)" == "$BASE" && -z "$(git status --porcelain)" ]] ||
 fail "Unexpected installed DEV 762 baseline"
systemctl is-active --quiet tracker.service || fail "DEV app service inactive"
git fetch origin "refs/heads/$REF:refs/remotes/origin/$REF"
[[ "$(git rev-parse "refs/remotes/origin/$REF")" == "$TARGET" ]] ||
 fail "Release ref moved"
git merge-base --is-ancestor "$BASE" "$TARGET" || fail "Not a descendant of 762"
[[ -z "$(git diff --name-only "$BASE" "$TARGET" -- \
  app/progress_models762.py app/models.py app/migrations.py app/db.py)" ]] ||
 fail "DEV 763 may not change schema tables"
STAGE="$(mktemp -d /tmp/tracker763-install.XXXXXXXX)"
trap 'rm -rf -- "$STAGE"' EXIT
RUNNER="$STAGE/runner.sh"
git show "$TARGET:scripts/tracker-release.sh" > "$RUNNER"
[[ "$(git hash-object "$RUNNER")" == "$(git rev-parse "$TARGET:scripts/tracker-release.sh")" ]] ||
 fail "Pinned runner object mismatch"
bash -n "$RUNNER"
bash "$RUNNER" --instance DEV --base "$BASE" --target "$TARGET" --ref "$REF"
[[ "$(git branch --show-current)" == main &&
   "$(git rev-parse HEAD)" == "$TARGET" &&
   -z "$(git status --porcelain)" ]] || fail "Installed DEV SHA mismatch"
systemctl is-active --quiet tracker.service || fail "DEV service inactive after install"
echo "RELEASE_763_DEV_INSTALL=SUCCESS"
