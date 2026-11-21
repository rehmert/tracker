#!/usr/bin/env bash
# Release 735: isolated signed PROD catch-up gates with additive 731 schema review; never install.
set -Eeuo pipefail
umask 077
APP=/opt/tracker
PY="$APP/.venv/bin/python"
BASE=2421fde33dfae626022529f046c9b21035ad6d62
REF=release/735-prod-catchup-727-to-735
fail() { echo "RELEASE_735_BLOCKED=$*" >&2; exit 1; }
[[ $# == 1 && "$1" =~ ^[0-9a-f]{40}$ ]] ||
  fail "Expected exact candidate SHA"
TARGET="$1"
[[ "$(id -u)" == 0 && "$(hostname -s)" == tracker-dev &&
   -n "${INVOCATION_ID:-}" ]] || fail "Root systemd worker on tracker-dev required"
[[ "$(readlink /proc/self/ns/net)" != "$(readlink /proc/1/ns/net)" ]] ||
  fail "PrivateNetwork=yes required"
[[ -x "$PY" && -d "$APP/.git" ]] || fail "Installed DEV source missing"
cd "$APP"
export GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=safe.directory
export GIT_CONFIG_VALUE_0="$APP"
[[ "$(git branch --show-current)" == main &&
   "$(git rev-parse HEAD)" == "$BASE" &&
   -z "$(git status --porcelain)" ]] ||
  fail "Clean installed Release 734 required"
systemctl is-active --quiet tracker || fail "Installed DEV service inactive"
exec 9>/run/lock/tracker735-prod-catchup-727-to-735.lock
flock -n 9 || fail "Another Release 735 QA active"
[[ "$(git rev-parse "refs/remotes/origin/$REF")" == "$TARGET" ]] ||
  fail "Fetched Release 735 branch SHA mismatch"
git merge-base --is-ancestor "$BASE" "$TARGET" ||
  fail "Candidate must descend from Release 734"
git diff --check "$BASE" "$TARGET"
while IFS= read -r path; do
  case "$path" in
    docs/release-735-prod-catchup.md|\
    scripts/tracker-install735.sh|\
    scripts/tracker-qualify735.sh|\
    scripts/tracker-release-scoped735.sh|\
    scripts/tracker-release.sh|\
    scripts/tracker_prod_remote568.sh|\
    scripts/tracker_schema_review735.py|\
    tests/test_release735_prod_catchup.py) ;;
    *) fail "Unexpected Release 735 source path: $path" ;;
  esac
done < <(git diff --name-only "$BASE" "$TARGET")
RUN="$(mktemp -d /tmp/tracker735-prod-catchup-727-to-735.XXXXXXXX)"
QA="$RUN/source"
cleanup() {
  local code=$?
  trap - EXIT
  if [[ -d "$QA" ]] &&
     ! git -C "$APP" worktree remove --force "$QA"; then
    echo "RELEASE_735_BLOCKED=Source worktree cleanup failed" >&2
    code=1
  fi
  rm -rf -- "$RUN"
  if [[ "$(git -C "$APP" rev-parse HEAD)" != "$BASE" ||
        "$(git -C "$APP" branch --show-current)" != main ||
        -n "$(git -C "$APP" status --porcelain)" ]]; then
    echo "RELEASE_735_BLOCKED=Installed DEV source changed" >&2
    code=1
  fi
  echo "RELEASE_735_INSTALLED_DEV=UNMODIFIED"
  echo "RELEASE_735_EXIT_STATUS=$code"
  exit "$code"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
git worktree add --detach "$QA" "$TARGET"
[[ "$(git -C "$QA" rev-parse HEAD)" == "$TARGET" ]] ||
  fail "QA worktree differs from exact target"
export GIT_CONFIG_COUNT=2
export GIT_CONFIG_KEY_0=safe.directory GIT_CONFIG_VALUE_0="$APP"
export GIT_CONFIG_KEY_1=safe.directory GIT_CONFIG_VALUE_1="$QA"
mkdir -m 700 "$RUN/data"
cd "$QA"
export TRACKER_DATA_DIR="$RUN/data" PYTHONPATH="$QA" PYTHONDONTWRITEBYTECODE=1
bash -n scripts/tracker-qualify735.sh
bash -n scripts/tracker-release-scoped735.sh
bash -n scripts/tracker-install735.sh
bash -n scripts/tracker-release.sh
bash -n scripts/tracker-browser-qualify.sh
bash -n scripts/tracker-release-scoped735.sh
"$PY" -B scripts/tracker-impact-preflight604.py \
  --base "$BASE" --target "$TARGET" --root "$QA"
"$PY" -B scripts/tracker_schema_review735.py \
  --root "$QA" --base 3718936aedfcb1b8fe243c86fe6fc7e06a7a41d2 --target "$TARGET"
echo "RELEASE_735_CATCHUP_REVIEW=PASSED"
echo "RELEASE_735_IMPACT_PREFLIGHT=PASSED"
bash scripts/tracker-release-scoped735.sh "$PY"
echo "RELEASE_735_QUALIFICATION=PASSED_SCOPED_NO_DEPLOY"
