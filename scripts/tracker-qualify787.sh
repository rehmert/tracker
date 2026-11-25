#!/usr/bin/env bash
# Release 787: exact-SHA, private, calendar action buttons qualification. No installation.
set -Eeuo pipefail
umask 077
APP=/opt/tracker
PY="$APP/.venv/bin/python"
BASE=8d78d2a01d5150102add2682e9fca51d60ea2790
REF=release/787-calendar-action-buttons
fail(){ echo "RELEASE_787_BLOCKED=$*" >&2; exit 1; }
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
 -z "$(git status --porcelain)" ]] || fail "Clean installed DEV 786 required"
systemctl is-active --quiet tracker.service || fail "DEV service inactive"
exec 9>/run/lock/tracker787-calendar-action-buttons-qa.lock
flock -n 9 || fail "Concurrent Release 787 qualification"
[[ "$(git rev-parse "refs/remotes/origin/$REF")" == "$TARGET" ]] ||
 fail "Release branch SHA changed"
git merge-base --is-ancestor "$BASE" "$TARGET" || fail "Non-descendant target"
git diff --check "$BASE" "$TARGET"
while IFS= read -r path; do
 case "$path" in
  AGENTS.md|\
  app/static/css/tracker-calendar-actions787.css|\
  app/templates/_calendar_vial_units756.html|\
  app/templates/_google_protocol_review783.html|\
  app/templates/calendar.html|\
  app/templates/calendar_quick_dose786.html|\
  tests/test_calendar_action_buttons787.py|\
  scripts/tracker-qualify787.sh|\
  scripts/tracker-install787.sh|\
  scripts/tracker-release-scoped787.sh|\
  __never__) ;;
  *) fail "Unreviewed changed path: $path";;
 esac
done < <(git diff --name-only "$BASE" "$TARGET")
[[ -z "$(git diff --name-only "$BASE" "$TARGET" -- app/models.py app/migrations.py app/db.py app/google_tasks_models769.py app/google_tasks_client769.py requirements.txt deploy/)" ]] ||
 fail "Unreviewed schema, OAuth or deployment change"
RUN="$(mktemp -d /tmp/tracker787-calendar-action-buttons.XXXXXXXX)"
QA="$RUN/source"
cleanup(){
 local rc=$?
 trap - EXIT
 if [[ -d "$QA" ]] && ! git -C "$APP" worktree remove --force "$QA"; then rc=1; fi
 rm -rf -- "$RUN"
 if [[ "$(git -C "$APP" rev-parse HEAD)" != "$BASE" ||
       "$(git -C "$APP" branch --show-current)" != main ||
       -n "$(git -C "$APP" status --porcelain)" ]]; then rc=1; fi
 echo "RELEASE_787_INSTALLED_DEV=UNMODIFIED"
 echo "RELEASE_787_EXIT_STATUS=$rc"
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
for file in scripts/tracker-qualify787.sh scripts/tracker-install787.sh scripts/tracker-release-scoped787.sh scripts/tracker-release.sh; do bash -n "$file"; done
"$PY" -B - <<'PYCODE'
import ast
from pathlib import Path
from jinja2 import Environment
for path in ("tests/test_calendar_action_buttons787.py",):
 ast.parse(Path(path).read_text(encoding="utf-8"), filename=path)
for path in ("app/templates/_calendar_vial_units756.html", "app/templates/_google_protocol_review783.html", "app/templates/calendar.html", "app/templates/calendar_quick_dose786.html",):
 Environment().parse(Path(path).read_text(encoding="utf-8"))
print("RELEASE_787_SYNTAX=PASSED")
PYCODE
"$PY" -B scripts/tracker-impact-preflight604.py --base "$BASE" --target "$TARGET" --root "$QA"
echo "RELEASE_787_IMPACT_PREFLIGHT=PASSED"
timeout 600 bash scripts/tracker-release-scoped787.sh "$PY"
echo "RELEASE_787_QUALIFICATION=PASSED_SCOPED_NO_DEPLOY"
