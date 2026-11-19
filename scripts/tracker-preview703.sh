#!/usr/bin/env bash
# Release 703: isolated DEV preview of Vitals/Compound edit form actions.
# Neither installation nor production promotion; empty disposable data only.
set -Eeuo pipefail
umask 077

APP=/opt/tracker
PY="$APP/.venv/bin/python"
BASE=5d4c2c44ad5afc7d7a5ce1ae5396a03aa48d1528
REF=release/703-mobile-edit-form-actions

fail() { echo "RELEASE_703_PREVIEW_ERROR=$*" >&2; exit 1; }
[[ "$(id -u)" == 0 && "$(hostname -s)" == tracker-dev &&
   -n "$(printenv INVOCATION_ID || true)" ]] ||
  fail "Must run as root systemd worker on tracker-dev"
[[ -x "$PY" && -d "$APP/.git" ]] ||
  fail "DEV Python or Git repository unavailable"
cd "$APP"
export GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=safe.directory GIT_CONFIG_VALUE_0="$APP"
[[ "$(git branch --show-current)" == main && -z "$(git status --porcelain)" ]] ||
  fail "Requires clean installed DEV main"
[[ "$(git rev-parse HEAD)" == "$BASE" ]] ||
  fail "Requires exact deployed Release 702 DEV baseline"
systemctl is-active --quiet tracker || fail "DEV Tracker service inactive"

git fetch origin "refs/heads/$REF:refs/remotes/origin/$REF"
TARGET="$(git rev-parse "refs/remotes/origin/$REF")"
git merge-base --is-ancestor "$BASE" "$TARGET" ||
  fail "Candidate must descend from pinned Release 702"
[[ "$(git rev-list --count "$BASE..$TARGET")" -ge 1 ]] ||
  fail "Candidate has no changes"
git diff --check "$BASE" "$TARGET"

# Fail closed: three presentation paths, two tests, two gates, one doc.
while IFS= read -r path; do
  case "$path" in
    app/templates/vitals_edit.html|\
    app/templates/compound_edit.html|\
    app/static/css/tracker-mobile-edit-actions703.css|\
    tests/test_mobile_edit_actions703.py|\
    tests/browser/test_mobile_edit_actions703.py|\
    scripts/tracker-release-scoped703.sh|\
    scripts/tracker-preview703.sh|\
    docs/release-703-mobile-edit-actions.md) ;;
    *) fail "Out-of-scope Release 703 path: $path" ;;
  esac
done < <(git diff --name-only "$BASE" "$TARGET")

RUN="$(mktemp -d /tmp/tracker-preview703.XXXXXXXX)"
QA="$RUN/candidate"
cleanup() {
  status=$?
  trap - EXIT
  if [[ -d "$QA" ]]; then
    git -C "$APP" worktree remove --force "$QA" >/dev/null 2>&1 || true
  fi
  rm -rf -- "$RUN"
  echo "RELEASE_703_PREVIEW_EXIT_STATUS=$status"
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

bash scripts/tracker-release-scoped703.sh "$PY"

# Actual Jinja templates with synthetic values (no HTTP or real records).
# 2 edit forms x 5 widths x 3 density modes x 2 schemes = 60 viewports;
# Vitals' real dirty/restore JS also runs without network requests.
"$PY" -m pytest -q --tb=short --maxfail=1 \
  tests/browser/test_mobile_edit_actions703.py \
  tests/test_integrated_mobile_browser673.py \
  tests/test_mobile_dock_pointer603.py

echo "RELEASE_703_FORM_BROWSER=PASSED"
echo "RELEASE_703_TEST_SCOPE=MOBILE_VITALS_COMPOUND_FOCUSED_NO_FULL_SUITE"
echo "RELEASE_703_PREVIEW_QUALIFIED=$TARGET"
echo "RELEASE_703_PREVIEW=PASSED_ISOLATED_NO_INSTALL"
