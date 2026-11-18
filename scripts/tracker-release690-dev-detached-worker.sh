#!/usr/bin/env bash
# Release 690: exact-commit DEV deployment only, with change-scoped qualification.
# Separate ops branch keeps the preview-qualified release candidate immutable.
set -Eeuo pipefail
umask 077
APP=/opt/tracker
BASE=ae8c75ef39ed26fa505be17e0d8b6152542cbf36
TARGET=6a8cd357e7e8925228d1a37c50572f93c4ec0943
REF=release/690-overview-card-density
PY="$APP/.venv/bin/python"
fail() { echo "RELEASE_690_DEV_ERROR=$*" >&2; exit 1; }
[[ -n "${INVOCATION_ID:-}" ]] || fail "Refusing foreground execution: start as detached systemd unit"
[[ "$(id -u)" == 0 && "$(hostname -s)" == tracker-dev ]] ||
  fail "Run as root on tracker-dev"
[[ -x "$PY" ]] || fail "Configured Python missing"
cd "$APP"
export GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=safe.directory GIT_CONFIG_VALUE_0="$APP"
[[ "$(git branch --show-current)" == main && -z "$(git status --porcelain)" ]] ||
  fail "DEV checkout must be clean main"
[[ "$(git rev-parse HEAD)" == "$BASE" ]] ||
  fail "DEV baseline differs from installed Release 689"
systemctl is-active --quiet tracker || fail "DEV Tracker service inactive"
git fetch origin "refs/heads/$REF:refs/remotes/origin/$REF"
[[ "$(git rev-parse "refs/remotes/origin/$REF")" == "$TARGET" ]] ||
  fail "Release branch moved since isolated qualification"
git merge-base --is-ancestor "$BASE" "$TARGET" ||
  fail "Target not descended from installed DEV baseline"
git diff --check "$BASE" "$TARGET"
EXPECTED="$(printf '%s\n' \
  app/static/css/tracker-overview-density690.css \
  app/templates/dashboard.html \
  scripts/tracker-preview690.sh \
  scripts/tracker-release-scoped690.sh \
  tests/test_overview_density690.py | LC_ALL=C sort)"
ACTUAL="$(git diff --name-only "$BASE" "$TARGET" | LC_ALL=C sort)"
[[ "$ACTUAL" == "$EXPECTED" ]] || fail "Unexpected source changes"
STAGE="$(mktemp -d /tmp/tracker-690-dev.XXXXXXXX)"
trap 'rm -rf -- "$STAGE"' EXIT
git show "$TARGET:scripts/tracker-release.sh" > "$STAGE/runner.sh"
EXPECTED_RUNNER_BLOB="$(git rev-parse "$TARGET:scripts/tracker-release.sh")"
ACTUAL_RUNNER_BLOB="$(git hash-object "$STAGE/runner.sh")"
[[ "$ACTUAL_RUNNER_BLOB" == "$EXPECTED_RUNNER_BLOB" ]] ||
  fail "Pinned deployment engine hash mismatch"
bash -n "$STAGE/runner.sh"
echo "RELEASE_690_TEST_SCOPE=FOCUSED_NO_FULL_SUITE"
echo "RELEASE_690_DEV_BASE=$BASE"
echo "RELEASE_690_DEV_TARGET=$TARGET"
bash "$STAGE/runner.sh" --instance DEV --base "$BASE" --target "$TARGET" --ref "$REF"
[[ "$(git rev-parse HEAD)" == "$TARGET" ]] || fail "Installed DEV SHA mismatch"
systemctl is-active --quiet tracker || fail "DEV service inactive after deployment"
LOG=/etc/tracker-release/release-690-dev.log
[[ -f "$LOG" && ! -L "$LOG" ]] || fail "Signed DEV receipt unavailable"
grep -Fxq "DEV_QUALIFIED_COMMIT=$TARGET" "$LOG" ||
  fail "DEV qualification receipt commit mismatch"
grep -Fxq "FOCUSED_RELEASE_GATE=PASSED" "$LOG" ||
  fail "Scoped qualification not recorded"
grep -Fxq "EXIT_STATUS=0" "$LOG" ||
  fail "DEV qualification receipt not successful"
echo "RELEASE_690_DEV_INSTALLED=$TARGET"
echo "RELEASE_690_DEV_DEPLOYMENT=SUCCESS"
echo "RELEASE_690_PROD_DEPLOYMENT=NOT_REQUESTED"
