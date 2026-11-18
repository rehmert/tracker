#!/usr/bin/env bash
# Release 693: immutable, isolated preview; never installs or touches live DB.
set -Eeuo pipefail
umask 077
APP=/opt/tracker
PY="$APP/.venv/bin/python"
BASE=696fe7f482436090df5342f76cd65b9fb5febad4
REF=release/693-retire-workout-qr-mapping-ui
fail(){ echo "RELEASE_693_PREVIEW_ERROR=$*" >&2; exit 1; }
[[ "$(id -u)" == 0 && "$(hostname -s)" == tracker-dev &&
   -n "$(printenv INVOCATION_ID || true)" ]] ||
  fail "Detached root systemd worker on tracker-dev required"
[[ -x "$PY" ]] || fail "Configured Python missing"
cd "$APP"
export GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=safe.directory GIT_CONFIG_VALUE_0="$APP"
[[ "$(git branch --show-current)" == main && -z "$(git status --porcelain)" ]] ||
  fail "Require clean DEV main"
[[ "$(git rev-parse HEAD)" == "$BASE" ]] || fail "DEV must be installed Release 692"
systemctl is-active --quiet tracker || fail "DEV Tracker service inactive"
git fetch origin "refs/heads/$REF:refs/remotes/origin/$REF"
TARGET="$(git rev-parse "refs/remotes/origin/$REF")"
git merge-base --is-ancestor "$BASE" "$TARGET" || fail "Candidate not derived from installed 692"
RUN="$(mktemp -d /tmp/tracker-preview693.XXXXXXXX)"
QA="$RUN/source"
cleanup(){
  rc=$?
  trap - EXIT
  if [[ -d "$QA" ]]; then git -C "$APP" worktree remove --force "$QA" >/dev/null 2>&1 || true; fi
  rm -rf -- "$RUN"
  echo "RELEASE_693_PREVIEW_EXIT_STATUS=$rc"
  exit "$rc"
}
trap cleanup EXIT
git worktree add --detach "$QA" "$TARGET"
export GIT_CONFIG_COUNT=2 GIT_CONFIG_KEY_0=safe.directory GIT_CONFIG_VALUE_0="$APP" GIT_CONFIG_KEY_1=safe.directory GIT_CONFIG_VALUE_1="$QA"
export PYTHONPATH="$QA" TRACKER_DATA_DIR="$RUN/test-data"
mkdir -p "$TRACKER_DATA_DIR"
cd "$QA"
git diff --check "$BASE" "$TARGET"
"$PY" scripts/tracker-workout-qr-retirement-review693.py \
  --root "$QA" --base "$BASE" --target "$TARGET"
"$PY" scripts/tracker-impact-preflight604.py \
  --base "$BASE" --target "$TARGET" --root "$QA"
bash scripts/tracker-release-scoped693.sh "$PY"
echo "RELEASE_693_PREVIEW_QUALIFIED=$TARGET"
echo "RELEASE_693_PREVIEW=PASSED_ISOLATED_NO_INSTALL"
