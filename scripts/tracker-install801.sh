#!/usr/bin/env bash
# Release 801 guarded DEV-only code install; no schema or Google connection.
set -Eeuo pipefail
umask 077
APP=/opt/tracker
BASE=0283ec3642a02add1de7bfb3ca3159e39dc2e6bb
REF=release/801-benchmark-compatibility
fail(){ echo "RELEASE_801_INSTALL_BLOCKED=$*" >&2; exit 1; }
[[ $# == 1 && "$1" =~ ^[0-9a-f]{40}$ ]] || fail "Exact SHA required"
TARGET="$1"
[[ "$(id -u)" == 0 && "$(hostname -s)" == tracker-dev ]] || fail "DEV only"
[[ -f /etc/tracker.env && -x "$APP/.venv/bin/python" ]] || fail "DEV missing"
cd "$APP"
export GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=safe.directory GIT_CONFIG_VALUE_0="$APP"
[[ "$(git branch --show-current)" == main &&
 "$(git rev-parse HEAD)" == "$BASE" && -z "$(git status --porcelain)" ]] ||
 fail "Unexpected DEV baseline"
systemctl is-active --quiet tracker.service || fail "DEV service inactive"
git fetch origin "refs/heads/$REF:refs/remotes/origin/$REF"
[[ "$(git rev-parse "refs/remotes/origin/$REF")" == "$TARGET" ]] ||
 fail "Pinned release branch moved"
git merge-base --is-ancestor "$BASE" "$TARGET" || fail "Non-descendant target"
[[ -z "$(git diff --name-only "$BASE" "$TARGET" -- app/models.py app/migrations.py app/db.py app/google_tasks_models769.py requirements.txt deploy/)" ]] ||
 fail "Unexpected schema/dependency changes"
STAGE="$(mktemp -d /tmp/tracker801-install.XXXXXXXX)"
trap 'rm -rf -- "$STAGE"' EXIT
RUNNER="$STAGE/runner.sh"
git show "$TARGET:scripts/tracker-release.sh" > "$RUNNER"
[[ "$(git hash-object "$RUNNER")" == "$(git rev-parse "$TARGET:scripts/tracker-release.sh")" ]] ||
 fail "Pinned runner integrity mismatch"
bash -n "$RUNNER"
bash "$RUNNER" --instance DEV --base "$BASE" --target "$TARGET" --ref "$REF"
[[ "$(git branch --show-current)" == main &&
 "$(git rev-parse HEAD)" == "$TARGET" && -z "$(git status --porcelain)" ]] ||
 fail "DEV installed SHA mismatch"
systemctl is-active --quiet tracker.service || fail "DEV inactive after installation"
echo "RELEASE_801_DEV_INSTALL=SUCCESS"
