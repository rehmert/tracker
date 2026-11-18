#!/usr/bin/env bash
# Release 690: isolated, exact-manifest preview; no application installation.
set -Eeuo pipefail
umask 077
APP=/opt/tracker
BASE=ae8c75ef39ed26fa505be17e0d8b6152542cbf36
REF=release/690-overview-card-density
PY="$APP/.venv/bin/python"
fail(){ echo "RELEASE_690_PREVIEW_ERROR=$*" >&2; exit 1; }
[[ -n "$(printenv INVOCATION_ID || true)" ]] || fail "Refusing foreground execution"
[[ "$(id -u)" == 0 && "$(hostname -s)" == tracker-dev ]] ||
  fail "Run as root on tracker-dev"
[[ -x "$PY" ]] || fail "Configured Python missing"
cd "$APP"
export GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=safe.directory GIT_CONFIG_VALUE_0="$APP"
[[ "$(git branch --show-current)" == main && -z "$(git status --porcelain)" ]] ||
  fail "Require clean installed DEV main"
[[ "$(git rev-parse HEAD)" == "$BASE" ]] ||
  fail "Require installed DEV Release 689"
git fetch origin "refs/heads/$REF:refs/remotes/origin/$REF"
TARGET="$(git rev-parse "refs/remotes/origin/$REF")"
git merge-base --is-ancestor "$BASE" "$TARGET" ||
  fail "Candidate not descended from Release 689"
RUN="$(mktemp -d /tmp/tracker-690-preview.XXXXXXXX)"
QA="$RUN/source"
cleanup(){
  code=$?
  trap - EXIT
  if [[ -d "$QA" ]]; then git -C "$APP" worktree remove --force "$QA" >/dev/null 2>&1 || true; fi
  rm -rf -- "$RUN"
  echo "RELEASE_690_PREVIEW_EXIT_STATUS=$code"
  exit "$code"
}
trap cleanup EXIT
git worktree add --detach "$QA" "$TARGET"
export GIT_CONFIG_COUNT=2 GIT_CONFIG_KEY_0=safe.directory GIT_CONFIG_VALUE_0="$APP" GIT_CONFIG_KEY_1=safe.directory GIT_CONFIG_VALUE_1="$QA"
export PYTHONPATH="$QA" TRACKER_DATA_DIR="$RUN/test-data"
mkdir -p "$TRACKER_DATA_DIR"
cd "$QA"
git diff --check "$BASE" "$TARGET"
EXPECTED="$(printf '%s\n' \
  app/static/css/tracker-overview-density690.css \
  app/templates/dashboard.html \
  scripts/tracker-preview690.sh \
  scripts/tracker-release-scoped690.sh \
  tests/test_overview_density690.py | LC_ALL=C sort)"
ACTUAL="$(git diff --name-only "$BASE" "$TARGET" | LC_ALL=C sort)"
[[ "$ACTUAL" == "$EXPECTED" ]] || fail "Unexpected source files in candidate"
"$PY" scripts/tracker-impact-preflight604.py --base "$BASE" --target "$TARGET" --root "$QA"
bash scripts/tracker-release-scoped690.sh "$PY"
echo "RELEASE_690_PREVIEW_QUALIFIED=$TARGET"
echo "RELEASE_690_PREVIEW=PASSED_ISOLATED_NO_INSTALL"
