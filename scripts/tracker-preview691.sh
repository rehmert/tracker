#!/usr/bin/env bash
# Release 691: detached-only preview, checked additive schema and focused tests.
set -Eeuo pipefail
umask 077
APP=/opt/tracker
BASE=6a8cd357e7e8925228d1a37c50572f93c4ec0943
REF=release/691-coa-document-identifiers
PY="$APP/.venv/bin/python"
fail(){ echo "RELEASE_691_PREVIEW_ERROR=$*" >&2; exit 1; }
[[ -n "$(printenv INVOCATION_ID || true)" ]] || fail "Foreground execution refused"
[[ "$(id -u)" == 0 && "$(hostname -s)" == tracker-dev ]] ||
  fail "Root on tracker-dev required"
[[ -x "$PY" ]] || fail "Configured Python missing"
cd "$APP"
export GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=safe.directory GIT_CONFIG_VALUE_0="$APP"
[[ "$(git branch --show-current)" == main && -z "$(git status --porcelain)" ]] ||
  fail "Require clean installed DEV main"
DEV_HEAD="$(git rev-parse HEAD)"
[[ "$DEV_HEAD" == "$BASE" || "$DEV_HEAD" == "ae8c75ef39ed26fa505be17e0d8b6152542cbf36" ]] ||
  fail "Require installed DEV Release 689 or 690; tests remain fully isolated"
git fetch origin "refs/heads/$REF:refs/remotes/origin/$REF"
TARGET="$(git rev-parse "refs/remotes/origin/$REF")"
git merge-base --is-ancestor "$BASE" "$TARGET" ||
  fail "Candidate not descended from Release 690"
RUN="$(mktemp -d /tmp/tracker-691-preview.XXXXXXXX)"
QA="$RUN/source"
cleanup(){
  code=$?
  trap - EXIT
  if [[ -d "$QA" ]]; then git -C "$APP" worktree remove --force "$QA" >/dev/null 2>&1 || true; fi
  rm -rf -- "$RUN"
  echo "RELEASE_691_PREVIEW_EXIT_STATUS=$code"
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
  app/models.py \
  app/migrations.py \
  app/routers/coas.py \
  app/static/css/tracker-coa-identifiers691.css \
  app/templates/coa_edit.html \
  scripts/tracker-release.sh \
  scripts/tracker_schema_review691.py \
  scripts/tracker-release-scoped691.sh \
  scripts/tracker-preview691.sh \
  tests/test_coa_document_identifiers691.py | LC_ALL=C sort)"
ACTUAL="$(git diff --name-only "$BASE" "$TARGET" | LC_ALL=C sort)"
[[ "$ACTUAL" == "$EXPECTED" ]] || fail "Unexpected source files in release"
"$PY" scripts/tracker_schema_review691.py --root "$APP" --base "$BASE" --target "$TARGET"
"$PY" scripts/tracker-impact-preflight604.py --base "$BASE" --target "$TARGET" --root "$QA"
bash scripts/tracker-release-scoped691.sh "$PY"
echo "RELEASE_691_PREVIEW_QUALIFIED=$TARGET"
echo "RELEASE_691_PREVIEW=PASSED_ISOLATED_NO_INSTALL"
