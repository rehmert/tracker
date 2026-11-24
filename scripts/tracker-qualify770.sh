#!/usr/bin/env bash
# Release 770: exact-SHA mock-only DEV qualification, no live Google network or deployment.
set -Eeuo pipefail
umask 077
APP=/opt/tracker
PY="$APP/.venv/bin/python"
BASE=9f3e1154f30d5b2711957f51c675006f666d3440
REF=release/770-google-tasks-prod-only-guard
fail(){ echo "RELEASE_770_BLOCKED=$*" >&2; exit 1; }
[[ $# == 1 && "$1" =~ ^[0-9a-f]{40}$ ]] || fail "Pinned target SHA required"
TARGET="$1"
[[ "$(id -u)" == 0 && "$(hostname -s)" == tracker-dev &&
  -n "$(printenv INVOCATION_ID || true)" ]] || fail "DEV systemd root worker required"
[[ "$(readlink /proc/self/ns/net)" != "$(readlink /proc/1/ns/net)" ]] ||
 fail "PrivateNetwork=yes required"
[[ -x "$PY" && -d "$APP/.git" ]] || fail "Installed DEV missing"
cd "$APP"
export GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=safe.directory GIT_CONFIG_VALUE_0="$APP"
[[ "$(git branch --show-current)" == main &&
  "$(git rev-parse HEAD)" == "$BASE" && -z "$(git status --porcelain)" ]] ||
 fail "Clean installed DEV Release 769 required"
systemctl is-active --quiet tracker.service || fail "DEV service inactive"
exec 9>/run/lock/tracker770-google-guard-qa.lock
flock -n 9 || fail "Concurrent Release 770 qualification"
[[ "$(git rev-parse "refs/remotes/origin/$REF")" == "$TARGET" ]] || fail "Pinned release moved"
git merge-base --is-ancestor "$BASE" "$TARGET" || fail "Not a descendant of DEV"
git diff --check "$BASE" "$TARGET"
while IFS= read -r path; do
 case "$path" in
  app/google_tasks_client769.py|\
  app/routers/google_tasks769.py|\
  app/templates/google_tasks769.html|\
  docs/release-769-google-tasks.md|\
  docs/release-770-google-tasks-prod-only.md|\
  tests/test_release770_google_prod_guard.py|\
  scripts/tracker-qualify770.sh|\
  scripts/tracker-install770.sh|\
  scripts/tracker-release-scoped770.sh|\
  __never__) ;;
  *) fail "Unreviewed path: $path";;
 esac
done < <(git diff --name-only "$BASE" "$TARGET")
[[ -z "$(git diff --name-only "$BASE" "$TARGET" -- app/models.py app/migrations.py app/db.py app/google_tasks_models769.py requirements.txt deploy/)" ]] ||
 fail "Unreviewed schema/dependency changes forbidden"
RUN="$(mktemp -d /tmp/tracker770-prod-guard-qa.XXXXXXXX)"
QA="$RUN/source"
cleanup(){
 local rc=$?
 trap - EXIT
 if [[ -d "$QA" ]] && ! git -C "$APP" worktree remove --force "$QA"; then rc=1; fi
 rm -rf -- "$RUN"
 if [[ "$(git -C "$APP" rev-parse HEAD)" != "$BASE" ||
       "$(git -C "$APP" branch --show-current)" != main ||
       -n "$(git -C "$APP" status --porcelain)" ]]; then rc=1; fi
 echo "RELEASE_770_INSTALLED_DEV=UNMODIFIED"
 echo "RELEASE_770_EXIT_STATUS=$rc"
 exit "$rc"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
git worktree add --detach "$QA" "$TARGET"
[[ "$(git -C "$QA" rev-parse HEAD)" == "$TARGET" ]] || fail "Isolated QA SHA mismatch"
export GIT_CONFIG_COUNT=2 GIT_CONFIG_KEY_0=safe.directory GIT_CONFIG_VALUE_0="$APP"
export GIT_CONFIG_KEY_1=safe.directory GIT_CONFIG_VALUE_1="$QA"
mkdir -m 700 "$RUN/data"
cd "$QA"
export TRACKER_DATA_DIR="$RUN/data" PYTHONPATH="$QA" PYTHONDONTWRITEBYTECODE=1
for s in scripts/tracker-qualify770.sh scripts/tracker-install770.sh scripts/tracker-release-scoped770.sh scripts/tracker-release.sh; do bash -n "$s"; done
"$PY" -B - <<'PYCODE'
import ast
from pathlib import Path
from jinja2 import Environment
for name in ("app/google_tasks_client769.py","app/routers/google_tasks769.py",
             "tests/test_release770_google_prod_guard.py"):
 ast.parse(Path(name).read_text(encoding="utf-8"),filename=name)
Environment().parse(Path("app/templates/google_tasks769.html").read_text(encoding="utf-8"))
print("RELEASE_770_SYNTAX=PASSED")
PYCODE
"$PY" -B scripts/tracker-impact-preflight604.py --base "$BASE" --target "$TARGET" --root "$QA"
echo "RELEASE_770_IMPACT_PREFLIGHT=PASSED"
timeout 600 bash scripts/tracker-release-scoped770.sh "$PY"
echo "RELEASE_770_QUALIFICATION=PASSED_SCOPED_NO_DEPLOY"
