#!/usr/bin/env bash
# Release 771 exact-SHA disposable DEV qualification; PROD migration review only.
set -Eeuo pipefail
umask 077
APP=/opt/tracker
PY="$APP/.venv/bin/python"
BASE=a236ef996c725a231b6420ebf41dd63bf506e8bc
REF=release/771-google-tasks-prod-schema-catchup
fail(){ echo "RELEASE_771_BLOCKED=$*" >&2; exit 1; }
[[ $# == 1 && "$1" =~ ^[0-9a-f]{40}$ ]] || fail "Exact SHA required"
TARGET="$1"
[[ "$(id -u)" == 0 && "$(hostname -s)" == tracker-dev &&
 -n "$(printenv INVOCATION_ID || true)" ]] || fail "Root DEV private systemd worker required"
[[ "$(readlink /proc/self/ns/net)" != "$(readlink /proc/1/ns/net)" ]] ||
 fail "PrivateNetwork=yes required"
[[ -x "$PY" && -d "$APP/.git" ]] || fail "Installed DEV missing"
cd "$APP"
export GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=safe.directory GIT_CONFIG_VALUE_0="$APP"
[[ "$(git branch --show-current)" == main &&
 "$(git rev-parse HEAD)" == "$BASE" && -z "$(git status --porcelain)" ]] ||
 fail "Clean installed DEV 770 required"
systemctl is-active --quiet tracker.service || fail "DEV service inactive"
exec 9>/run/lock/tracker771-google-prod-catchup-qa.lock
flock -n 9 || fail "Concurrent Release 771 qualification"
[[ "$(git rev-parse "refs/remotes/origin/$REF")" == "$TARGET" ]] ||
 fail "Release ref SHA changed"
git merge-base --is-ancestor "$BASE" "$TARGET" || fail "Not a descendant"
git diff --check "$BASE" "$TARGET"
while IFS= read -r path; do
 case "$path" in
  scripts/tracker-prod-google-schema771.py|\
  scripts/tracker_prod_remote568.sh|\
  tests/test_release771_google_prod_catchup.py|\
  docs/release-771-google-tasks-prod-schema.md|\
  scripts/tracker-qualify771.sh|\
  scripts/tracker-install771.sh|\
  scripts/tracker-release-scoped771.sh|\
  __never__) ;;
  *) fail "Unreviewed source path: $path";;
 esac
done < <(git diff --name-only "$BASE" "$TARGET")
[[ -z "$(git diff --name-only "$BASE" "$TARGET" -- app/ requirements.txt deploy/ alembic/)" ]] ||
 fail "Existing application and schema must be identical to DEV 770"
RUN="$(mktemp -d /tmp/tracker771-google-prod-catchup.XXXXXXXX)"
QA="$RUN/source"
cleanup(){
 local rc=$?
 trap - EXIT
 if [[ -d "$QA" ]] && ! git -C "$APP" worktree remove --force "$QA"; then rc=1; fi
 rm -rf -- "$RUN"
 if [[ "$(git -C "$APP" rev-parse HEAD)" != "$BASE" ||
       "$(git -C "$APP" branch --show-current)" != main ||
       -n "$(git -C "$APP" status --porcelain)" ]]; then rc=1; fi
 echo "RELEASE_771_INSTALLED_DEV=UNMODIFIED"
 echo "RELEASE_771_EXIT_STATUS=$rc"
 exit "$rc"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
git worktree add --detach "$QA" "$TARGET"
[[ "$(git -C "$QA" rev-parse HEAD)" == "$TARGET" ]] || fail "QA detached SHA mismatch"
export GIT_CONFIG_COUNT=2 GIT_CONFIG_KEY_0=safe.directory GIT_CONFIG_VALUE_0="$APP"
export GIT_CONFIG_KEY_1=safe.directory GIT_CONFIG_VALUE_1="$QA"
mkdir -m 700 "$RUN/data"
cd "$QA"
export TRACKER_DATA_DIR="$RUN/data" PYTHONPATH="$QA" PYTHONDONTWRITEBYTECODE=1
for s in scripts/tracker-qualify771.sh scripts/tracker-install771.sh scripts/tracker-release-scoped771.sh scripts/tracker_prod_remote568.sh scripts/tracker-release.sh; do
 bash -n "$s"
done
"$PY" -B - <<'PYCODE'
import ast
from pathlib import Path
for name in ("scripts/tracker-prod-google-schema771.py",
             "tests/test_release771_google_prod_catchup.py"):
 ast.parse(Path(name).read_text(encoding="utf-8"), filename=name)
print("RELEASE_771_SYNTAX=PASSED")
PYCODE
"$PY" -B scripts/tracker-impact-preflight604.py --base "$BASE" --target "$TARGET" --root "$QA"
echo "RELEASE_771_IMPACT_PREFLIGHT=PASSED"
timeout 600 bash scripts/tracker-release-scoped771.sh "$PY"
echo "RELEASE_771_QUALIFICATION=PASSED_SCOPED_NO_DEPLOY"
