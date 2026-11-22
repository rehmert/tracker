#!/usr/bin/env bash
# Release 750 exact-SHA private-network candidate QA; never deploy.
set -Eeuo pipefail
umask 077
APP=/opt/tracker
PY="$APP/.venv/bin/python"
BASE=e80edbfa5ef5c7d41a953be36c60c4828b4a86d7
REF=release/750-offline-browser-multiuser-acceptance
fail(){ echo "RELEASE_750_BLOCKED=$*" >&2; exit 1; }
[[ $# == 1 && "$1" =~ ^[0-9a-f]{40}$ ]] || fail "Exact SHA required"
TARGET="$1"
[[ "$(id -u)" == 0 && "$(hostname -s)" == tracker-dev &&
   -n "$(printenv INVOCATION_ID || true)" ]] || fail "Root systemd worker required"
[[ "$(readlink /proc/self/ns/net)" != "$(readlink /proc/1/ns/net)" ]] ||
 fail "PrivateNetwork=yes required"
[[ -x "$PY" && -d "$APP/.git" ]] || fail "Installed DEV missing"
cd "$APP"
export GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=safe.directory
export GIT_CONFIG_VALUE_0="$APP"
[[ "$(git branch --show-current)" == main &&
  "$(git rev-parse HEAD)" == "$BASE" &&
  -z "$(git status --porcelain)" ]] || fail "DEV Release 749 not clean"
systemctl is-active --quiet tracker || fail "DEV service inactive"
exec 9>/run/lock/tracker750-acceptance.lock
flock -n 9 || fail "Concurrent Release 750 QA"
[[ "$(git rev-parse "refs/remotes/origin/$REF")" == "$TARGET" ]] ||
 fail "Pinned branch target mismatch"
git merge-base --is-ancestor "$BASE" "$TARGET" || fail "Not fast forward"
git diff --check "$BASE" "$TARGET"
while IFS= read -r path; do
 case "$path" in
 scripts/tracker_browser_restore750.py|scripts/tracker-release-scoped750.sh|\
 scripts/tracker-qualify750.sh|scripts/tracker-install750.sh|\
 tests/test_release750_acceptance.py|docs/release-750-evidence.md) ;;
 *) fail "Unreviewed path: $path" ;;
 esac
done < <(git diff --name-only "$BASE" "$TARGET")
RUN="$(mktemp -d /tmp/tracker750-acceptance.XXXXXXXX)"
QA="$RUN/source"
cleanup(){
 local rc=$?
 trap - EXIT
 if [[ -d "$QA" ]] &&
    ! git -C "$APP" worktree remove --force "$QA"; then rc=1; fi
 rm -rf -- "$RUN"
 if [[ "$(git -C "$APP" rev-parse HEAD)" != "$BASE" ||
       "$(git -C "$APP" branch --show-current)" != main ||
       -n "$(git -C "$APP" status --porcelain)" ]]; then rc=1; fi
 echo "RELEASE_750_INSTALLED_DEV=UNMODIFIED"
 echo "RELEASE_750_EXIT_STATUS=$rc"
 exit "$rc"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
git worktree add --detach "$QA" "$TARGET"
[[ "$(git -C "$QA" rev-parse HEAD)" == "$TARGET" ]] ||
 fail "Worktree target differs"
export GIT_CONFIG_COUNT=2 GIT_CONFIG_KEY_0=safe.directory
export GIT_CONFIG_VALUE_0="$APP" GIT_CONFIG_KEY_1=safe.directory
export GIT_CONFIG_VALUE_1="$QA"
mkdir -m 700 "$RUN/data"
cd "$QA"
export TRACKER_DATA_DIR="$RUN/data" PYTHONPATH="$QA" PYTHONDONTWRITEBYTECODE=1
"$PY" -B scripts/tracker-impact-preflight604.py \
 --base "$BASE" --target "$TARGET" --root "$QA"
echo "RELEASE_750_IMPACT_PREFLIGHT=PASSED"
bash scripts/tracker-release-scoped750.sh "$PY"
echo "RELEASE_750_QUALIFICATION=PASSED_SCOPED_NO_DEPLOY"
