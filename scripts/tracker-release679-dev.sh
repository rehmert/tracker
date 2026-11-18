#!/usr/bin/env bash
# Release 679: install exact isolated-qualified candidate on DEV ONLY.
# This operator helper is on ops/679-dev-deploy, separate from the pinned candidate.
set -Eeuo pipefail
umask 077
APP=/opt/tracker
BASE=b0a40f02837b6221b9d9474bdc74ac6a7c7835b0
TARGET=a24bb47e0193ce7ca61b6d095ab055f37082aaf7
REF=release/679-ui-foundation
fail(){ echo "RELEASE_679_DEV_ERROR=$*" >&2; exit 1; }
[[ "$(id -u)" == 0 && "$(hostname -s)" == tracker-dev ]] || fail "Run as root on tracker-dev only"
[[ -x "$APP/.venv/bin/python" ]] || fail "Missing Tracker Python"
cd "$APP"
export GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=safe.directory GIT_CONFIG_VALUE_0="$APP"
[[ "$(git branch --show-current)" == main && -z "$(git status --porcelain)" ]] || fail "DEV checkout must be clean main"
[[ "$(git rev-parse HEAD)" == "$BASE" ]] || fail "Installed DEV baseline differs from Release 678"
systemctl is-active --quiet tracker || fail "DEV Tracker service inactive"
git fetch origin main "refs/heads/$REF:refs/remotes/origin/$REF"
[[ "$(git rev-parse origin/main)" == "$BASE" ]] || fail "GitHub main differs from qualified baseline"
[[ "$(git rev-parse "refs/remotes/origin/$REF")" == "$TARGET" ]] || fail "Release branch moved since preview; requalify"
git merge-base --is-ancestor "$BASE" "$TARGET" || fail "Candidate does not descend from baseline"
git diff --check "$BASE" "$TARGET"
EXPECTED_FILES="$(printf '%s\n' \
  app/static/css/tracker-ui-foundation679.css \
  app/templates/base.html \
  docs/release-679-ui-foundation.md \
  scripts/tracker-preview679.sh \
  scripts/tracker-release-scoped679.sh \
  scripts/tracker-visual-capture679.py \
  tests/test_ui_foundation679.py | LC_ALL=C sort)"
ACTUAL_FILES="$(git diff --name-only "$BASE" "$TARGET" | LC_ALL=C sort)"
[[ "$ACTUAL_FILES" == "$EXPECTED_FILES" ]] || fail "Unexpected candidate file set"
STAGE="$(mktemp -d /tmp/tracker-679-dev.XXXXXXXX)"
trap 'rm -rf -- "$STAGE"' EXIT
git show "$TARGET:scripts/tracker-release.sh" > "$STAGE/runner.sh"
[[ "$(git hash-object "$STAGE/runner.sh")" == "$(git rev-parse "$TARGET:scripts/tracker-release.sh")" ]] || fail "Release runner hash mismatch"
bash -n "$STAGE/runner.sh"
echo "RELEASE_679_DEV_PINNED_BASE=$BASE"
echo "RELEASE_679_DEV_PINNED_TARGET=$TARGET"
echo "RELEASE_679_TEST_SCOPE=FOCUSED_NO_FULL_SUITE"
bash "$STAGE/runner.sh" --instance DEV --base "$BASE" --target "$TARGET" --ref "$REF"
[[ "$(git rev-parse HEAD)" == "$TARGET" ]] || fail "DEV installed commit mismatch"
systemctl is-active --quiet tracker || fail "DEV service inactive"
LOG=/etc/tracker-release/release-679-dev.log
[[ -f "$LOG" && ! -L "$LOG" ]] || fail "Missing DEV qualification receipt"
grep -Fxq "DEV_QUALIFIED_COMMIT=$TARGET" "$LOG" || fail "Commit receipt mismatch"
grep -Fxq "FOCUSED_RELEASE_GATE=PASSED" "$LOG" || fail "Focused qualification missing"
grep -Fxq "EXIT_STATUS=0" "$LOG" || fail "Release receipt not successful"
echo "RELEASE_679_DEV_INSTALLED=$TARGET"
echo "RELEASE_679_DEV_DEPLOYMENT=SUCCESS"
echo "RELEASE_679_PROD_DEPLOYMENT=NOT_REQUESTED"
