#!/usr/bin/env bash
# Release 749: isolated exact-SHA DEV qualification only, never install.
set -Eeuo pipefail
umask 077
APP=/opt/tracker
PY="$APP/.venv/bin/python"
BASE=bd59b6e84ded0e55f91c5d88908ef2a1372ea429
REF=release/749-portrait-sidebar-fit
fail() { echo "RELEASE_749_BLOCKED=$*" >&2; exit 1; }
[[ $# == 1 && "$1" =~ ^[0-9a-f]{40}$ ]] || fail "Expected pinned SHA"
TARGET="$1"
[[ "$(id -u)" == 0 && "$(hostname -s)" == tracker-dev &&
   -n "$(printenv INVOCATION_ID || true)" ]] ||
  fail "Root systemd worker on tracker-dev required"
[[ "$(readlink /proc/self/ns/net)" != "$(readlink /proc/1/ns/net)" ]] ||
  fail "PrivateNetwork=yes required"
[[ -x "$PY" && -d "$APP/.git" ]] || fail "Installed DEV missing"
cd "$APP"
export GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=safe.directory
export GIT_CONFIG_VALUE_0="$APP"
[[ "$(git branch --show-current)" == main &&
   "$(git rev-parse HEAD)" == "$BASE" &&
   -z "$(git status --porcelain)" ]] ||
  fail "Clean installed Release 748 required"
systemctl is-active --quiet tracker || fail "DEV service inactive"
exec 9>/run/lock/tracker749-sidebar-qa.lock
flock -n 9 || fail "Another Release 749 QA active"
[[ "$(git rev-parse "refs/remotes/origin/$REF")" == "$TARGET" ]] ||
  fail "Fetched release SHA mismatch"
git merge-base --is-ancestor "$BASE" "$TARGET" || fail "Not descended from 748"
git diff --check "$BASE" "$TARGET"
while IFS= read -r path; do
  case "$path" in
    app/templates/base.html|\
    app/static/css/tracker-mobile-drawer749.css|\
    tests/test_release749_mobile_drawer.py|\
    scripts/tracker-qualify749.sh|\
    scripts/tracker-release-scoped749.sh|\
    scripts/tracker-install749.sh|\
    docs/release-749-mobile-drawer.md) ;;
    *) fail "Unexpected source path: $path" ;;
  esac
done < <(git diff --name-only "$BASE" "$TARGET")
RUN="$(mktemp -d /tmp/tracker749-sidebar-qa.XXXXXXXX)"
QA="$RUN/source"
cleanup() {
  local code=$?
  trap - EXIT
  if [[ -d "$QA" ]] &&
     ! git -C "$APP" worktree remove --force "$QA"; then
    echo "RELEASE_749_BLOCKED=Worktree cleanup failed" >&2
    code=1
  fi
  rm -rf -- "$RUN"
  if [[ "$(git -C "$APP" rev-parse HEAD)" != "$BASE" ||
        "$(git -C "$APP" branch --show-current)" != main ||
        -n "$(git -C "$APP" status --porcelain)" ]]; then
    echo "RELEASE_749_BLOCKED=Installed DEV changed during QA" >&2
    code=1
  fi
  echo "RELEASE_749_INSTALLED_DEV=UNMODIFIED"
  echo "RELEASE_749_EXIT_STATUS=$code"
  exit "$code"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
git worktree add --detach "$QA" "$TARGET"
[[ "$(git -C "$QA" rev-parse HEAD)" == "$TARGET" ]] ||
  fail "Source differs from target SHA"
export GIT_CONFIG_COUNT=2
export GIT_CONFIG_KEY_0=safe.directory GIT_CONFIG_VALUE_0="$APP"
export GIT_CONFIG_KEY_1=safe.directory GIT_CONFIG_VALUE_1="$QA"
mkdir -m 700 "$RUN/data"
cd "$QA"
export TRACKER_DATA_DIR="$RUN/data" PYTHONPATH="$QA" PYTHONDONTWRITEBYTECODE=1
"$PY" -B scripts/tracker-impact-preflight604.py \
  --base "$BASE" --target "$TARGET" --root "$QA"
echo "RELEASE_749_IMPACT_PREFLIGHT=PASSED"
bash scripts/tracker-release-scoped749.sh "$PY"
echo "RELEASE_749_QUALIFICATION=PASSED_SCOPED_NO_DEPLOY"
