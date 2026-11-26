#!/usr/bin/env bash
# Release 792: exact-SHA, private, consolidated food, gym, inventory and health workspaces qualification. No installation.
set -Eeuo pipefail
umask 077
APP=/opt/tracker
PY="$APP/.venv/bin/python"
BASE=0a5ba934a415451ad462bc7594cd4178d558d20d
REF=release/792-consolidated-workspaces
fail(){ echo "RELEASE_792_BLOCKED=$*" >&2; exit 1; }
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
 -z "$(git status --porcelain)" ]] || fail "Clean installed DEV 791 required"
systemctl is-active --quiet tracker.service || fail "DEV service inactive"
exec 9>/run/lock/tracker792-consolidated-workspaces-qa.lock
flock -n 9 || fail "Concurrent Release 792 qualification"
[[ "$(git rev-parse "refs/remotes/origin/$REF")" == "$TARGET" ]] ||
 fail "Release branch SHA changed"
git merge-base --is-ancestor "$BASE" "$TARGET" || fail "Non-descendant target"
git diff --check "$BASE" "$TARGET"
while IFS= read -r path; do
 case "$path" in
  app/routers/food.py|\
  app/routers/food_bundle376.py|\
  app/routers/health_insights.py|\
  app/static/css/tracker-workspaces792.css|\
  app/static/js/tracker-protocol-dashboard-3494.js|\
  app/static/js/tracker-workspaces792.js|\
  app/templates/_workspace792.html|\
  app/templates/base.html|\
  app/templates/blends.html|\
  app/templates/dashboard.html|\
  app/templates/food.html|\
  app/templates/health_insights.html|\
  app/templates/health_timeline.html|\
  app/templates/inventory_health.html|\
  app/templates/labs.html|\
  app/templates/progress762.html|\
  app/templates/protocols.html|\
  app/templates/purchases.html|\
  app/templates/report_trends766.html|\
  app/templates/vials.html|\
  app/templates/vitals.html|\
  app/templates/workout_quick659.html|\
  tests/test_consolidated_workspaces792.py|\
  tests/test_food_mobile424.py|\
  tests/test_food_order383.py|\
  tests/test_integrated_mobile_ux673.py|\
  tests/test_release722_gym_focus.py|\
  scripts/tracker-qualify792.sh|\
  scripts/tracker-install792.sh|\
  scripts/tracker-release-scoped792.sh|\
  __never__) ;;
  *) fail "Unreviewed changed path: $path";;
 esac
done < <(git diff --name-only "$BASE" "$TARGET")
[[ -z "$(git diff --name-only "$BASE" "$TARGET" -- app/models.py app/migrations.py app/db.py app/google_tasks_models769.py app/google_tasks_client769.py requirements.txt deploy/)" ]] ||
 fail "Unreviewed schema, OAuth or deployment change"
RUN="$(mktemp -d /tmp/tracker792-consolidated-workspaces.XXXXXXXX)"
QA="$RUN/source"
cleanup(){
 local rc=$?
 trap - EXIT
 if [[ -d "$QA" ]] && ! git -C "$APP" worktree remove --force "$QA"; then rc=1; fi
 rm -rf -- "$RUN"
 if [[ "$(git -C "$APP" rev-parse HEAD)" != "$BASE" ||
       "$(git -C "$APP" branch --show-current)" != main ||
       -n "$(git -C "$APP" status --porcelain)" ]]; then rc=1; fi
 echo "RELEASE_792_INSTALLED_DEV=UNMODIFIED"
 echo "RELEASE_792_EXIT_STATUS=$rc"
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
for file in scripts/tracker-qualify792.sh scripts/tracker-install792.sh scripts/tracker-release-scoped792.sh scripts/tracker-release.sh; do bash -n "$file"; done
"$PY" -B - <<'PYCODE'
import ast
from pathlib import Path
from jinja2 import Environment
for path in ("app/routers/food.py", "app/routers/food_bundle376.py", "app/routers/health_insights.py", "tests/test_consolidated_workspaces792.py", "tests/test_food_mobile424.py", "tests/test_food_order383.py", "tests/test_integrated_mobile_ux673.py", "tests/test_release722_gym_focus.py",):
 ast.parse(Path(path).read_text(encoding="utf-8"), filename=path)
for path in ("app/templates/_workspace792.html", "app/templates/base.html", "app/templates/blends.html", "app/templates/dashboard.html", "app/templates/food.html", "app/templates/health_insights.html", "app/templates/health_timeline.html", "app/templates/inventory_health.html", "app/templates/labs.html", "app/templates/progress762.html", "app/templates/protocols.html", "app/templates/purchases.html", "app/templates/report_trends766.html", "app/templates/vials.html", "app/templates/vitals.html", "app/templates/workout_quick659.html",):
 Environment().parse(Path(path).read_text(encoding="utf-8"))
print("RELEASE_792_SYNTAX=PASSED")
PYCODE
"$PY" -B scripts/tracker-impact-preflight604.py --base "$BASE" --target "$TARGET" --root "$QA"
echo "RELEASE_792_IMPACT_PREFLIGHT=PASSED"
timeout 600 bash scripts/tracker-release-scoped792.sh "$PY"
echo "RELEASE_792_QUALIFICATION=PASSED_SCOPED_NO_DEPLOY"
