#!/usr/bin/env bash
# Release 702: pinned 701 baseline, detached saved-food mobile actions preview.
# Offline Chromium synthetic Jinja page, disposable SQLite, no install or PROD.
set -Eeuo pipefail
umask 077

APP=/opt/tracker
PY="$APP/.venv/bin/python"
BASE=afba8b1f810d777927679cb6feaaa043396f805d
REF=release/702-saved-food-mobile-actions

fail() { echo "RELEASE_702_PREVIEW_ERROR=$*" >&2; exit 1; }
[[ "$(id -u)" == 0 && "$(hostname -s)" == tracker-dev &&
   -n "$(printenv INVOCATION_ID || true)" ]] ||
  fail "Must run only as root systemd worker on tracker-dev"
[[ -x "$PY" && -d "$APP/.git" ]] || fail "DEV Python/repository unavailable"
cd "$APP"
export GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=safe.directory GIT_CONFIG_VALUE_0="$APP"
[[ "$(git branch --show-current)" == main && -z "$(git status --porcelain)" ]] ||
  fail "Require clean installed DEV main"
[[ "$(git rev-parse HEAD)" == "$BASE" ]] ||
  fail "DEV must be on exact successfully deployed Release 701"
systemctl is-active --quiet tracker || fail "Installed DEV Tracker service inactive"

git fetch origin "refs/heads/$REF:refs/remotes/origin/$REF"
TARGET="$(git rev-parse "refs/remotes/origin/$REF")"
git merge-base --is-ancestor "$BASE" "$TARGET" ||
  fail "Candidate must descend from pinned Release 701"
[[ "$(git rev-list --count "$BASE..$TARGET")" -ge 1 ]] ||
  fail "No candidate changes"
git diff --check "$BASE" "$TARGET"

# Fail-closed seven-path list; the application change is one form and one CSS.
while IFS= read -r path; do
  case "$path" in
    app/templates/food_saved_edit669.html|\
    app/static/css/tracker-saved-food-actions702.css|\
    tests/test_saved_food_mobile_actions702.py|\
    tests/browser/test_saved_food_mobile_actions702.py|\
    scripts/tracker-preview702.sh|\
    scripts/tracker-release-scoped702.sh|\
    docs/release-702-saved-food-mobile-actions.md) ;;
    *) fail "Out-of-scope Release 702 path: $path" ;;
  esac
done < <(git diff --name-only "$BASE" "$TARGET")

RUN="$(mktemp -d /tmp/tracker-preview702.XXXXXXXX)"
QA="$RUN/candidate"
cleanup() {
  status=$?
  trap - EXIT
  git -C "$APP" worktree remove --force "$QA" >/dev/null 2>&1 || true
  rm -rf -- "$RUN"
  echo "RELEASE_702_PREVIEW_EXIT_STATUS=$status"
  exit "$status"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

git worktree add --detach "$QA" "$TARGET"
export GIT_CONFIG_COUNT=2 \
  GIT_CONFIG_KEY_0=safe.directory GIT_CONFIG_VALUE_0="$APP" \
  GIT_CONFIG_KEY_1=safe.directory GIT_CONFIG_VALUE_1="$QA"

mkdir -m 700 "$RUN/test-data"
export PYTHONPATH="$QA" TRACKER_DATA_DIR="$RUN/test-data"
cd "$QA"

bash scripts/tracker-release-scoped702.sh "$PY"

# Test the rendered real Saved Food Jinja form (synthetic values) and
# actual mobile CSS/JS, at 320/390/430/760/1024 widths, 3 densities and
# 2 themes. No HTTP or writes: Save is preventDefault in this fixture.
"$PY" -m pytest -q --tb=short --maxfail=1 \
  tests/browser/test_saved_food_mobile_actions702.py \
  tests/test_integrated_mobile_browser673.py \
  tests/test_mobile_dock_pointer603.py

echo "RELEASE_702_FORM_BROWSER=PASSED"
echo "RELEASE_702_TEST_SCOPE=SAVED_FOOD_MOBILE_FOCUSED_NO_FULL_SUITE"
echo "RELEASE_702_PREVIEW_QUALIFIED=$TARGET"
echo "RELEASE_702_PREVIEW=PASSED_ISOLATED_NO_INSTALL"
