#!/usr/bin/env bash
# Release 783: exact-SHA, private, Google completion and vitals qualification. No installation.
set -Eeuo pipefail
umask 077
APP=/opt/tracker
PY="$APP/.venv/bin/python"
BASE=edb792410539e5186e5b6c186d5b5c7ce8d137a5
REF=release/783-google-protocol-review
fail(){ echo "RELEASE_783_BLOCKED=$*" >&2; exit 1; }
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
 -z "$(git status --porcelain)" ]] || fail "Clean installed DEV 782 required"
systemctl is-active --quiet tracker.service || fail "DEV service inactive"
exec 9>/run/lock/tracker783-google-protocol-review-qa.lock
flock -n 9 || fail "Concurrent Release 783 qualification"
[[ "$(git rev-parse "refs/remotes/origin/$REF")" == "$TARGET" ]] ||
 fail "Release branch SHA changed"
git merge-base --is-ancestor "$BASE" "$TARGET" || fail "Non-descendant target"
git diff --check "$BASE" "$TARGET"
while IFS= read -r path; do
 case "$path" in
  app/google_protocol_review783.py|\
 |\
  app/routers/calendar.py|\
  app/routers/dashboard.py|\
  app/routers/google_tasks769.py|\
  app/routers/vitals.py|\
  app/static/css/tracker-vitals-tools.css|\
  app/static/js/tracker-calendar-workbench.js|\
  app/static/js/tracker-vitals-tools.js|\
  app/templates/_google_protocol_review783.html|\
  app/templates/calendar.html|\
  app/templates/dashboard.html|\
  app/templates/google_tasks769.html|\
  app/templates/vitals.html|\
  app/templates/vitals_edit.html|\
  tests/test_calendar_workbench.py|\
  tests/test_release783_reconciliation.py|\
  tests/test_vitals_date_review.py|\
  scripts/tracker-qualify783.sh|\
  scripts/tracker-install783.sh|\
  scripts/tracker-release-scoped783.sh|\
  __never__) ;;
  *) fail "Unreviewed changed path: $path";;
 esac
done < <(git diff --name-only "$BASE" "$TARGET")
[[ -z "$(git diff --name-only "$BASE" "$TARGET" -- app/models.py app/migrations.py app/db.py app/google_tasks_models769.py app/google_tasks_client769.py app/google_tasks_sync769.py requirements.txt deploy/)" ]] ||
 fail "Unreviewed schema, OAuth or deployment change"
RUN="$(mktemp -d /tmp/tracker783-google-protocol-review.XXXXXXXX)"
QA="$RUN/source"
cleanup(){
 local rc=$?
 trap - EXIT
 if [[ -d "$QA" ]] && ! git -C "$APP" worktree remove --force "$QA"; then rc=1; fi
 rm -rf -- "$RUN"
 if [[ "$(git -C "$APP" rev-parse HEAD)" != "$BASE" ||
       "$(git -C "$APP" branch --show-current)" != main ||
       -n "$(git -C "$APP" status --porcelain)" ]]; then rc=1; fi
 echo "RELEASE_783_INSTALLED_DEV=UNMODIFIED"
 echo "RELEASE_783_EXIT_STATUS=$rc"
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
for file in scripts/tracker-qualify783.sh scripts/tracker-install783.sh scripts/tracker-release-scoped783.sh scripts/tracker-release.sh; do bash -n "$file"; done
"$PY" -B - <<'PYCODE'
import ast
from pathlib import Path
from jinja2 import Environment
for path in ("app/google_protocol_review783.py", "app/google_tasks_sync769.py", "app/routers/calendar.py", "app/routers/dashboard.py", "app/routers/google_tasks769.py", "app/routers/vitals.py", "tests/test_calendar_workbench.py", "tests/test_release783_reconciliation.py", "tests/test_vitals_date_review.py",):
 ast.parse(Path(path).read_text(encoding="utf-8"), filename=path)
for path in ("app/templates/_google_protocol_review783.html", "app/templates/calendar.html", "app/templates/dashboard.html", "app/templates/google_tasks769.html", "app/templates/vitals.html", "app/templates/vitals_edit.html",):
 Environment().parse(Path(path).read_text(encoding="utf-8"))
print("RELEASE_783_SYNTAX=PASSED")
PYCODE
"$PY" -B scripts/tracker-impact-preflight604.py --base "$BASE" --target "$TARGET" --root "$QA"
echo "RELEASE_783_IMPACT_PREFLIGHT=PASSED"
timeout 600 bash scripts/tracker-release-scoped783.sh "$PY"
echo "RELEASE_783_QUALIFICATION=PASSED_SCOPED_NO_DEPLOY"
