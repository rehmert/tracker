#!/usr/bin/env bash
# Release 760 exact-SHA, disposable DEV qualification. No installed-source or data writes.
set -Eeuo pipefail
umask 077
APP=/opt/tracker
PY="$APP/.venv/bin/python"
BASE=eb1d3ab3c66aa8d2c8af8cc7ae4ed85bf4d2357d
REF=release/760-prod-schema-catchup
fail(){ echo "RELEASE_760_BLOCKED=$*" >&2; exit 1; }
[[ $# == 1 && "$1" =~ ^[0-9a-f]{40}$ ]] || fail "Exact candidate SHA required"
TARGET="$1"
[[ "$(id -u)" == 0 && "$(hostname -s)" == tracker-dev &&
 -n "$(printenv INVOCATION_ID || true)" ]] || fail "Root DEV systemd worker required"
[[ "$(readlink /proc/self/ns/net)" != "$(readlink /proc/1/ns/net)" ]] ||
 fail "PrivateNetwork=yes required"
[[ -x "$PY" && -d "$APP/.git" ]] || fail "Installed DEV missing"
cd "$APP"
export GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=safe.directory
export GIT_CONFIG_VALUE_0="$APP"
[[ "$(git branch --show-current)" == main &&
 "$(git rev-parse HEAD)" == "$BASE" &&
 -z "$(git status --porcelain)" ]] || fail "Clean Release 759 installed DEV base required"
systemctl is-active --quiet tracker.service || fail "DEV service inactive"
exec 9>/run/lock/tracker760-prod-catchup-qa.lock
flock -n 9 || fail "Concurrent Release 760 qualification"
[[ "$(git rev-parse "refs/remotes/origin/$REF")" == "$TARGET" ]] ||
 fail "Release branch does not match pinned SHA"
git merge-base --is-ancestor "$BASE" "$TARGET" || fail "Non-descendant candidate"
git diff --check "$BASE" "$TARGET"
while IFS= read -r path; do
 case "$path" in
  scripts/tracker_prod_remote568.sh|\
  scripts/tracker-qualify760.sh|\
  scripts/tracker-install760.sh|\
  scripts/tracker-release-scoped760.sh|\
  docs/release-760-prod-schema-catchup.md|\
  tests/test_release760_prod_catchup.py) ;;
  *) fail "Unreviewed release path: $path" ;;
 esac
done < <(git diff --name-only "$BASE" "$TARGET")
RUN="$(mktemp -d /tmp/tracker760-prod-catchup-qa.XXXXXXXX)"
QA="$RUN/source"
cleanup(){
 local rc=$?
 trap - EXIT
 if [[ -d "$QA" ]] && ! git -C "$APP" worktree remove --force "$QA"; then rc=1; fi
 rm -rf -- "$RUN"
 if [[ "$(git -C "$APP" rev-parse HEAD)" != "$BASE" ||
       "$(git -C "$APP" branch --show-current)" != main ||
       -n "$(git -C "$APP" status --porcelain)" ]]; then rc=1; fi
 echo "RELEASE_760_INSTALLED_DEV=UNMODIFIED"
 echo "RELEASE_760_EXIT_STATUS=$rc"
 exit "$rc"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
git worktree add --detach "$QA" "$TARGET"
[[ "$(git -C "$QA" rev-parse HEAD)" == "$TARGET" ]] || fail "Detached QA SHA mismatch"
export GIT_CONFIG_COUNT=2 GIT_CONFIG_KEY_0=safe.directory
export GIT_CONFIG_VALUE_0="$APP" GIT_CONFIG_KEY_1=safe.directory
export GIT_CONFIG_VALUE_1="$QA"
mkdir -m 700 "$RUN/data"
cd "$QA"
export TRACKER_DATA_DIR="$RUN/data" PYTHONPATH="$QA" PYTHONDONTWRITEBYTECODE=1
for script in scripts/tracker-qualify760.sh scripts/tracker-install760.sh scripts/tracker-release-scoped760.sh scripts/tracker-release.sh scripts/tracker_prod_remote568.sh; do
 bash -n "$script"
done
"$PY" -B - <<'PYCODE'
import ast
from pathlib import Path
files = (
    "tests/test_release760_prod_catchup.py",
)
for filename in files:
    ast.parse(Path(filename).read_text(encoding="utf-8"), filename=filename)
print("RELEASE_760_SYNTAX=PASSED")
PYCODE
"$PY" -B scripts/tracker-impact-preflight604.py --base "$BASE" --target "$TARGET" --root "$QA"
echo "RELEASE_760_IMPACT_PREFLIGHT=PASSED"
timeout 600 bash scripts/tracker-release-scoped760.sh "$PY"
echo "RELEASE_760_QUALIFICATION=PASSED_SCOPED_NO_DEPLOY"
