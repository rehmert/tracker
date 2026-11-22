#!/usr/bin/env bash
# Release 748: concurrent Work-task coordination contract and guarded scoped regressions; never install.
set -Eeuo pipefail
umask 077
APP=/opt/tracker
PY="$APP/.venv/bin/python"
BASE=a0a42cd345f15e61e6a44a20e151271b1ccb0e08
REF=release/748-mobile-macd-dependency
fail() { echo "RELEASE_748_BLOCKED=$*" >&2; exit 1; }
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
  fail "Clean installed Release 747 required"
systemctl is-active --quiet tracker || fail "Installed DEV service inactive"
exec 9>/run/lock/tracker748-release-coordination.lock
flock -n 9 || fail "Another Release 748 QA active"
[[ "$(git rev-parse "refs/remotes/origin/$REF")" == "$TARGET" ]] ||
  fail "Fetched Release 748 branch SHA mismatch"
git merge-base --is-ancestor "$BASE" "$TARGET" ||
  fail "Candidate must descend from Release 747"
git diff --check "$BASE" "$TARGET"
while IFS= read -r path; do
  case "$path" in
    app/templates/page_history.html|\
    scripts/tracker_browser_elf748.py|\
    tests/test_release748_host_evidence.py|\
    tests/test_release748_macd_mobile.py|\
    docs/release-748-combined-acceptance.md|\
    scripts/tracker-qualify748.sh|\
    scripts/tracker-install748.sh|\
    scripts/tracker-release-scoped748.sh) ;;
    *) fail "Unexpected Release 748 source path: $path" ;;
  esac
done < <(git diff --name-only "$BASE" "$TARGET")
RUN="$(mktemp -d /tmp/tracker748-release-coordination.XXXXXXXX)"
QA="$RUN/source"
cleanup() {
  local code=$?
  trap - EXIT
  if [[ -d "$QA" ]] &&
     ! git -C "$APP" worktree remove --force "$QA"; then
    echo "RELEASE_748_BLOCKED=Source worktree cleanup failed" >&2
    code=1
  fi
  rm -rf -- "$RUN"
  if [[ "$(git -C "$APP" rev-parse HEAD)" != "$BASE" ||
        "$(git -C "$APP" branch --show-current)" != main ||
        -n "$(git -C "$APP" status --porcelain)" ]]; then
    echo "RELEASE_748_BLOCKED=Installed DEV source changed" >&2
    code=1
  fi
  echo "RELEASE_748_INSTALLED_DEV=UNMODIFIED"
  echo "RELEASE_748_EXIT_STATUS=$code"
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
bash -n scripts/tracker-qualify748.sh
bash -n scripts/tracker-release-scoped748.sh
bash -n scripts/tracker-install748.sh
bash -n scripts/tracker-release.sh
bash -n scripts/tracker-browser-qualify.sh
bash -n scripts/tracker-release-scoped748.sh
"$PY" -B scripts/tracker-impact-preflight604.py \
  --base "$BASE" --target "$TARGET" --root "$QA"
echo "RELEASE_748_IMPACT_PREFLIGHT=PASSED"
bash scripts/tracker-release-scoped748.sh "$PY"
echo "RELEASE_748_QUALIFICATION=PASSED_SCOPED_NO_DEPLOY"
