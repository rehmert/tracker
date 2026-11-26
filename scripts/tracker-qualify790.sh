#!/usr/bin/env bash
# Release 790: exact-SHA, private, integrated daily workspace qualification. No installation.
set -Eeuo pipefail
umask 077
APP=/opt/tracker
PY="$APP/.venv/bin/python"
BASE=9c8ae0b40dbb0e4e9500b378c8240376a46d58e6
REF=release/790-integrated-daily-workspace
fail(){ echo "RELEASE_790_BLOCKED=$*" >&2; exit 1; }
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
 -z "$(git status --porcelain)" ]] || fail "Clean installed DEV 789 required"
systemctl is-active --quiet tracker.service || fail "DEV service inactive"
exec 9>/run/lock/tracker790-integrated-daily-workspace-qa.lock
flock -n 9 || fail "Concurrent Release 790 qualification"
[[ "$(git rev-parse "refs/remotes/origin/$REF")" == "$TARGET" ]] ||
 fail "Release branch SHA changed"
git merge-base --is-ancestor "$BASE" "$TARGET" || fail "Non-descendant target"
git diff --check "$BASE" "$TARGET"
while IFS= read -r path; do
 case "$path" in
  AGENTS.md|\
  app/calendar_quick_dose786.py|\
  app/daily_workspace790.py|\
  app/routers/calendar.py|\
  app/routers/dashboard.py|\
  app/routers/doses.py|\
  app/routers/google_tasks769.py|\
  app/routers/mobile509.py|\
  app/routers/regimen635.py|\
  app/static/css/tracker-daily-workspace790.css|\
  app/static/css/tracker-mobile-quick528.css|\
  app/static/js/tracker-calendar-views374.js|\
  app/static/js/tracker-daily-workspace790.js|\
  app/static/js/tracker-mobile-quick528.js|\
  app/static/tracker_focus.js|\
  app/templates/_google_protocol_review783.html|\
  app/templates/_regimen_today790.html|\
  app/templates/_ui790.html|\
  app/templates/base.html|\
  app/templates/calendar.html|\
  app/templates/calendar_quick_dose786.html|\
  app/templates/dashboard.html|\
  app/templates/mobile_today509.html|\
  app/templates/quick_entry.html|\
  app/templates/regimen635.html|\
  tests/test_calendar_action_buttons787.py|\
  tests/test_dashboard_dose_shortcuts.py|\
  tests/test_integrated_daily790.py|\
  tests/test_mobile_quick528.py|\
  tests/test_mobile_quick_actions701.py|\
  tests/test_release765_daily_actions.py|\
  tests/test_release776_google_tasks_focus.py|\
  tests/test_spacing529.py|\
  scripts/tracker-qualify790.sh|\
  scripts/tracker-install790.sh|\
  scripts/tracker-release-scoped790.sh|\
  __never__) ;;
  *) fail "Unreviewed changed path: $path";;
 esac
done < <(git diff --name-only "$BASE" "$TARGET")
[[ -z "$(git diff --name-only "$BASE" "$TARGET" -- app/models.py app/migrations.py app/db.py app/google_tasks_models769.py app/google_tasks_client769.py requirements.txt deploy/)" ]] ||
 fail "Unreviewed schema, OAuth or deployment change"
RUN="$(mktemp -d /tmp/tracker790-integrated-daily-workspace.XXXXXXXX)"
QA="$RUN/source"
cleanup(){
 local rc=$?
 trap - EXIT
 if [[ -d "$QA" ]] && ! git -C "$APP" worktree remove --force "$QA"; then rc=1; fi
 rm -rf -- "$RUN"
 if [[ "$(git -C "$APP" rev-parse HEAD)" != "$BASE" ||
       "$(git -C "$APP" branch --show-current)" != main ||
       -n "$(git -C "$APP" status --porcelain)" ]]; then rc=1; fi
 echo "RELEASE_790_INSTALLED_DEV=UNMODIFIED"
 echo "RELEASE_790_EXIT_STATUS=$rc"
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
for file in scripts/tracker-qualify790.sh scripts/tracker-install790.sh scripts/tracker-release-scoped790.sh scripts/tracker-release.sh; do bash -n "$file"; done
"$PY" -B - <<'PYCODE'
import ast
from pathlib import Path
from jinja2 import Environment
for path in ("app/calendar_quick_dose786.py", "app/daily_workspace790.py", "app/routers/calendar.py", "app/routers/dashboard.py", "app/routers/doses.py", "app/routers/google_tasks769.py", "app/routers/mobile509.py", "app/routers/regimen635.py", "tests/test_calendar_action_buttons787.py", "tests/test_dashboard_dose_shortcuts.py", "tests/test_integrated_daily790.py", "tests/test_mobile_quick528.py", "tests/test_mobile_quick_actions701.py", "tests/test_release765_daily_actions.py", "tests/test_release776_google_tasks_focus.py", "tests/test_spacing529.py",):
 ast.parse(Path(path).read_text(encoding="utf-8"), filename=path)
for path in ("app/templates/_google_protocol_review783.html", "app/templates/_regimen_today790.html", "app/templates/_ui790.html", "app/templates/base.html", "app/templates/calendar.html", "app/templates/calendar_quick_dose786.html", "app/templates/dashboard.html", "app/templates/mobile_today509.html", "app/templates/quick_entry.html", "app/templates/regimen635.html",):
 Environment().parse(Path(path).read_text(encoding="utf-8"))
print("RELEASE_790_SYNTAX=PASSED")
PYCODE
"$PY" -B scripts/tracker-impact-preflight604.py --base "$BASE" --target "$TARGET" --root "$QA"
echo "RELEASE_790_IMPACT_PREFLIGHT=PASSED"
timeout 600 bash scripts/tracker-release-scoped790.sh "$PY"
echo "RELEASE_790_QUALIFICATION=PASSED_SCOPED_NO_DEPLOY"
