#!/usr/bin/env bash
# Release 766 exact-SHA, disposable DEV qualification. No installed-source or data writes.
set -Eeuo pipefail
umask 077
APP=/opt/tracker
PY="$APP/.venv/bin/python"
BASE=8c67580611fd945d9ae83f8015f071a24ab6fee5
REF=release/766-mobile-recipes-device-trends
fail(){ echo "RELEASE_766_BLOCKED=$*" >&2; exit 1; }
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
 -z "$(git status --porcelain)" ]] || fail "Clean Release 765 installed DEV base required"
systemctl is-active --quiet tracker.service || fail "DEV service inactive"
exec 9>/run/lock/tracker766-integrated-qa.lock
flock -n 9 || fail "Concurrent Release 766 qualification"
[[ "$(git rev-parse "refs/remotes/origin/$REF")" == "$TARGET" ]] ||
 fail "Release branch does not match pinned SHA"
git merge-base --is-ancestor "$BASE" "$TARGET" || fail "Non-descendant candidate"
git diff --check "$BASE" "$TARGET"
while IFS= read -r path; do
 case "$path" in
  app/device_models766.py|\
  app/main.py|\
  app/routers/device_import766.py|\
  app/routers/food_recipes766.py|\
  app/routers/report_trends766.py|\
  app/static/css/tracker-device-import766.css|\
  app/static/css/tracker-gym-handoff766.css|\
  app/static/css/tracker-recipes766.css|\
  app/static/css/tracker-trends766.css|\
  app/static/css/tracker-vial-mobile-cards766.css|\
  app/static/js/tracker-gym-handoff766.js|\
  app/static/js/tracker-vial-mobile-cards766.js|\
  app/templates/consolidated_reports.html|\
  app/templates/device_import766.html|\
  app/templates/food.html|\
  app/templates/food_recipes766.html|\
  app/templates/mobile_today509.html|\
  app/templates/progress762.html|\
  app/templates/quick_entry.html|\
  app/templates/report_trends766.html|\
  app/templates/vials.html|\
  app/templates/workout_quick659.html|\
  tests/browser/test_release766_mobile.py|\
  tests/test_release766_combined.py|\
  docs/release-766-integrated-mobile-food-data-reports.md|\
  scripts/tracker-qualify766.sh|\
  scripts/tracker-install766.sh|\
  scripts/tracker-release-scoped766.sh) ;;
  *) fail "Unreviewed release path: $path" ;;
 esac
done < <(git diff --name-only "$BASE" "$TARGET")
RUN="$(mktemp -d /tmp/tracker766-integrated-qa.XXXXXXXX)"
QA="$RUN/source"
cleanup(){
 local rc=$?
 trap - EXIT
 if [[ -d "$QA" ]] && ! git -C "$APP" worktree remove --force "$QA"; then rc=1; fi
 rm -rf -- "$RUN"
 if [[ "$(git -C "$APP" rev-parse HEAD)" != "$BASE" ||
       "$(git -C "$APP" branch --show-current)" != main ||
       -n "$(git -C "$APP" status --porcelain)" ]]; then rc=1; fi
 echo "RELEASE_766_INSTALLED_DEV=UNMODIFIED"
 echo "RELEASE_766_EXIT_STATUS=$rc"
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
for script in scripts/tracker-qualify766.sh scripts/tracker-install766.sh scripts/tracker-release-scoped766.sh scripts/tracker-release.sh; do
 bash -n "$script"
done
for asset in app/static/js/tracker-gym-handoff766.js app/static/js/tracker-vial-mobile-cards766.js; do
 node --check "$asset"
done
"$PY" -B - <<'PYCODE'
import ast
from pathlib import Path
files = (
    "app/main.py",
    "app/device_models766.py",
    "app/routers/device_import766.py",
    "app/routers/food_recipes766.py",
    "app/routers/report_trends766.py",
    "tests/test_release766_combined.py",
    "tests/browser/test_release766_mobile.py",
)
for filename in files:
    ast.parse(Path(filename).read_text(encoding="utf-8"), filename=filename)
print("RELEASE_766_SYNTAX=PASSED")
PYCODE
"$PY" -B - <<'PYCODE'
from pathlib import Path
from jinja2 import Environment
for path in (
    "app/templates/vials.html",
    "app/templates/workout_quick659.html",
    "app/templates/food.html",
    "app/templates/food_recipes766.html",
    "app/templates/device_import766.html",
    "app/templates/report_trends766.html",
    "app/templates/quick_entry.html",
    "app/templates/progress762.html",
    "app/templates/consolidated_reports.html",
    "app/templates/mobile_today509.html",
):
    Environment().parse(Path(path).read_text(encoding="utf-8"))
for path in (
    "app/static/css/tracker-device-import766.css",
    "app/static/css/tracker-gym-handoff766.css",
    "app/static/css/tracker-recipes766.css",
    "app/static/css/tracker-trends766.css",
    "app/static/css/tracker-vial-mobile-cards766.css",
):
    css = Path(path).read_text(encoding="utf-8")
    assert css.count("{") == css.count("}"), path
print("RELEASE_766_TEMPLATES_CSS=PASSED")
PYCODE
"$PY" -B scripts/tracker-impact-preflight604.py --base "$BASE" --target "$TARGET" --root "$QA"
echo "RELEASE_766_IMPACT_PREFLIGHT=PASSED"
timeout 600 bash scripts/tracker-release-scoped766.sh "$PY"
echo "RELEASE_766_QUALIFICATION=PASSED_SCOPED_NO_DEPLOY"
