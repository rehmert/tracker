#!/usr/bin/env bash
# Release 794: exact-SHA, private, consolidated planning and daily workflows qualification. No installation.
set -Eeuo pipefail
umask 077
APP=/opt/tracker
PY="$APP/.venv/bin/python"
BASE=8dafeb3eab7355780719c24c6de3d18d30b2d1bc
REF=release/794-workflow-consolidation
fail(){ echo "RELEASE_794_BLOCKED=$*" >&2; exit 1; }
[[ $# == 1 && "$1" =~ ^[0-9a-f]{40}$ ]] || fail "Exact target SHA required"
TARGET="$1"
[[ "$(id -u)" == 0 && "$(hostname -s)" == tracker-dev &&
 -n "$(printenv INVOCATION_ID || true)" ]] || fail "DEV root systemd worker required"
[[ "$(readlink /proc/self/ns/net)" != "$(readlink /proc/1/ns/net)" ]] ||
 fail "PrivateNetwork=yes required"
[[ -x "$PY" && -d "$APP/.git" ]] || fail "DEV checkout or Python missing"
cd "$APP"
export GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=safe.directory GIT_CONFIG_VALUE_0="$APP"
[[ "$(git branch --show-current)" == main && "$(git rev-parse HEAD)" == "$BASE" &&
 -z "$(git status --porcelain)" ]] || fail "Clean installed DEV 793 required"
systemctl is-active --quiet tracker.service || fail "DEV service inactive"
exec 9>/run/lock/tracker794-workflow-consolidation-qa.lock
flock -n 9 || fail "Concurrent Release 794 qualification"
[[ "$(git rev-parse "refs/remotes/origin/$REF")" == "$TARGET" ]] ||
 fail "Release branch SHA changed"
git merge-base --is-ancestor "$BASE" "$TARGET" || fail "Non-descendant target"
git diff --check "$BASE" "$TARGET"
while IFS= read -r path; do
 case "$path" in
  app/routers/labs.py|\
  app/routers/planning_hub.py|\
  app/routers/regimen635.py|\
  app/static/css/tracker-home794.css|\
  app/static/js/tracker-gym-handoff766.js|\
  app/templates/_workspace792.html|\
  app/templates/base.html|\
  app/templates/dashboard.html|\
  app/templates/doses.html|\
  app/templates/inventory_planning794.html|\
  app/templates/labs.html|\
  app/templates/mobile_today509.html|\
  app/templates/planning_hub.html|\
  app/templates/protocol_edit.html|\
  app/templates/regimen635.html|\
  app/templates/workout_quick659.html|\
  tests/test_release766_combined.py|\
  tests/test_release775_google_tasks_navigation.py|\
  tests/test_workflow_consolidation794.py|\
  scripts/tracker-qualify794.sh|\
  scripts/tracker-install794.sh|\
  scripts/tracker-release-scoped794.sh|\
  __never__) ;;
  *) fail "Unreviewed changed path: $path";;
 esac
done < <(git diff --name-only "$BASE" "$TARGET")
[[ -z "$(git diff --name-only "$BASE" "$TARGET" -- app/models.py app/migrations.py app/db.py app/google_tasks_models769.py app/google_tasks_client769.py requirements.txt deploy/)" ]] ||
 fail "Unreviewed schema, OAuth or deployment change"
RUN="$(mktemp -d /tmp/tracker794-workflow-consolidation.XXXXXXXX)"
QA="$RUN/source"
cleanup(){
 local rc=$?
 trap - EXIT
 if [[ -d "$QA" ]] && ! git -C "$APP" worktree remove --force "$QA"; then rc=1; fi
 rm -rf -- "$RUN"
 if [[ "$(git -C "$APP" rev-parse HEAD)" != "$BASE" ||
       "$(git -C "$APP" branch --show-current)" != main ||
       -n "$(git -C "$APP" status --porcelain)" ]]; then rc=1; fi
 echo "RELEASE_794_INSTALLED_DEV=UNMODIFIED"
 echo "RELEASE_794_EXIT_STATUS=$rc"
 exit "$rc"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
git worktree add --detach "$QA" "$TARGET"
[[ "$(git -C "$QA" rev-parse HEAD)" == "$TARGET" ]] || fail "QA SHA mismatch"
export GIT_CONFIG_COUNT=2 GIT_CONFIG_KEY_0=safe.directory GIT_CONFIG_VALUE_0="$APP"
export GIT_CONFIG_KEY_1=safe.directory GIT_CONFIG_VALUE_1="$QA"
mkdir -m 700 "$RUN/data"
cd "$QA"
export TRACKER_DATA_DIR="$RUN/data" PYTHONPATH="$QA" PYTHONDONTWRITEBYTECODE=1
for file in scripts/tracker-qualify794.sh scripts/tracker-install794.sh scripts/tracker-release-scoped794.sh scripts/tracker-release.sh; do bash -n "$file"; done
"$PY" -B - <<'PYCODE'
import ast
from pathlib import Path
from jinja2 import Environment
for path in ("app/routers/labs.py", "app/routers/planning_hub.py", "app/routers/regimen635.py", "tests/test_release766_combined.py", "tests/test_release775_google_tasks_navigation.py", "tests/test_workflow_consolidation794.py",):
 ast.parse(Path(path).read_text(encoding="utf-8"), filename=path)
for path in ("app/templates/_workspace792.html", "app/templates/base.html", "app/templates/dashboard.html", "app/templates/doses.html", "app/templates/inventory_planning794.html", "app/templates/labs.html", "app/templates/mobile_today509.html", "app/templates/planning_hub.html", "app/templates/protocol_edit.html", "app/templates/regimen635.html", "app/templates/workout_quick659.html",):
 Environment().parse(Path(path).read_text(encoding="utf-8"))
print("RELEASE_794_SYNTAX=PASSED")
PYCODE
"$PY" -B scripts/tracker-impact-preflight604.py --base "$BASE" --target "$TARGET" --root "$QA"
echo "RELEASE_794_IMPACT_PREFLIGHT=PASSED"
timeout 600 bash scripts/tracker-release-scoped794.sh "$PY"
echo "RELEASE_794_QUALIFICATION=PASSED_SCOPED_NO_DEPLOY"
