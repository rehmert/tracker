#!/usr/bin/env bash
# Release 742: isolated shared CSS consolidation, notes/supply read bounds and UX; never install.
set -Eeuo pipefail
umask 077
APP=/opt/tracker
PY="$APP/.venv/bin/python"
BASE=c5efed6b40f4324187eff3e83dbed44d9e68f5c4
REF=release/742-consolidated-ux-performance
fail() { echo "RELEASE_742_BLOCKED=$*" >&2; exit 1; }
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
  fail "Clean installed Release 741 required"
systemctl is-active --quiet tracker || fail "Installed DEV service inactive"
exec 9>/run/lock/tracker742-integrated-macd-mobile.lock
flock -n 9 || fail "Another Release 742 QA active"
[[ "$(git rev-parse "refs/remotes/origin/$REF")" == "$TARGET" ]] ||
  fail "Fetched Release 742 branch SHA mismatch"
git merge-base --is-ancestor "$BASE" "$TARGET" ||
  fail "Candidate must descend from Release 741"
git diff --check "$BASE" "$TARGET"
while IFS= read -r path; do
  case "$path" in
    app/routers/pages.py|\\
    app/routers/supplies.py|\\
    app/templates/supplies.html|\\
    app/templates/calendar.html|\\
    app/static/css/tracker-supplies-bundle742.css|\\
    app/static/css/tracker-calendar-bundle742.css|\\
    tests/test_release742_consolidated_ux_performance.py|\\
    scripts/tracker-qualify742.sh|\\
    scripts/tracker-install742.sh|\\
    scripts/tracker-release-scoped742.sh|\\
    docs/release-742-consolidated-ux-performance.md) ;;
    *) fail "Unexpected Release 742 source path: $path" ;;
  esac
done < <(git diff --name-only "$BASE" "$TARGET")
RUN="$(mktemp -d /tmp/tracker742-integrated-macd-mobile.XXXXXXXX)"
QA="$RUN/source"
cleanup() {
  local code=$?
  trap - EXIT
  if [[ -d "$QA" ]] &&
     ! git -C "$APP" worktree remove --force "$QA"; then
    echo "RELEASE_742_BLOCKED=Source worktree cleanup failed" >&2
    code=1
  fi
  rm -rf -- "$RUN"
  if [[ "$(git -C "$APP" rev-parse HEAD)" != "$BASE" ||
        "$(git -C "$APP" branch --show-current)" != main ||
        -n "$(git -C "$APP" status --porcelain)" ]]; then
    echo "RELEASE_742_BLOCKED=Installed DEV source changed" >&2
    code=1
  fi
  echo "RELEASE_742_INSTALLED_DEV=UNMODIFIED"
  echo "RELEASE_742_EXIT_STATUS=$code"
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
bash -n scripts/tracker-qualify742.sh
bash -n scripts/tracker-release-scoped742.sh
bash -n scripts/tracker-install742.sh
bash -n scripts/tracker-release.sh
bash -n scripts/tracker-browser-qualify.sh
bash -n scripts/tracker-release-scoped742.sh
"$PY" -B scripts/tracker-impact-preflight604.py \
  --base "$BASE" --target "$TARGET" --root "$QA"
echo "RELEASE_742_IMPACT_PREFLIGHT=PASSED"
bash scripts/tracker-release-scoped742.sh "$PY"
echo "RELEASE_742_QUALIFICATION=PASSED_SCOPED_NO_DEPLOY"
