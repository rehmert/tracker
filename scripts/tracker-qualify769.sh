#!/usr/bin/env bash
# Release 769 exact-SHA, private-network, disposable qualification. No deployment.
set -Eeuo pipefail
umask 077
APP=/opt/tracker
PY="$APP/.venv/bin/python"
BASE=62a78b4f0b79f2f6762976c1231cab2f5f593f25
REF=release/769-google-tasks-medications-supplements-protocols
fail(){ echo "RELEASE_769_BLOCKED=$*" >&2; exit 1; }
[[ $# == 1 && "$1" =~ ^[0-9a-f]{40}$ ]] || fail "Exact SHA required"
TARGET="$1"
[[ "$(id -u)" == 0 && "$(hostname -s)" == tracker-dev &&
 -n "$(printenv INVOCATION_ID || true)" ]] || fail "Root DEV systemd worker required"
[[ "$(readlink /proc/self/ns/net)" != "$(readlink /proc/1/ns/net)" ]] ||
 fail "PrivateNetwork=yes required"
[[ -x "$PY" && -d "$APP/.git" ]] || fail "Installed DEV missing"
cd "$APP"
export GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=safe.directory GIT_CONFIG_VALUE_0="$APP"
[[ "$(git branch --show-current)" == main &&
 "$(git rev-parse HEAD)" == "$BASE" && -z "$(git status --porcelain)" ]] ||
 fail "Clean installed Release 768 required"
systemctl is-active --quiet tracker.service || fail "DEV service inactive"
exec 9>/run/lock/tracker769-google-tasks-qa.lock
flock -n 9 || fail "Concurrent Release 769 qualification"
[[ "$(git rev-parse "refs/remotes/origin/$REF")" == "$TARGET" ]] ||
 fail "Release ref SHA mismatch"
git merge-base --is-ancestor "$BASE" "$TARGET" || fail "Non-descendant candidate"
git diff --check "$BASE" "$TARGET"
while IFS= read -r path; do
 case "$path" in
  app/google_tasks_models769.py|\
  app/google_tasks_projection769.py|\
  app/google_tasks_client769.py|\
  app/google_tasks_sync769.py|\
  app/google_tasks_background769.py|\
  app/routers/google_tasks769.py|\
  app/templates/google_tasks769.html|\
  app/main.py|\
  app/templates/regimen635.html|\
  app/templates/protocols.html|\
  tests/test_release769_google_tasks.py|\
  docs/release-769-google-tasks.md|\
  scripts/tracker-qualify769.sh|\
  scripts/tracker-install769.sh|\
  scripts/tracker-release-scoped769.sh|\
  __never__) ;;
  *) fail "Unreviewed path: $path";;
 esac
done < <(git diff --name-only "$BASE" "$TARGET")
# Exact additive table introduction only; old ORM models remain untouched.
[[ -z "$(git diff --name-only "$BASE" "$TARGET" -- app/models.py app/migrations.py app/db.py app/progress_models762.py app/device_models766.py requirements.txt deploy/)" ]] ||
 fail "Existing schema/dependency/deploy changes forbidden"
RUN="$(mktemp -d /tmp/tracker769-google-tasks-qa.XXXXXXXX)"
QA="$RUN/source"
cleanup(){
 local rc=$?
 trap - EXIT
 if [[ -d "$QA" ]] && ! git -C "$APP" worktree remove --force "$QA"; then rc=1; fi
 rm -rf -- "$RUN"
 if [[ "$(git -C "$APP" rev-parse HEAD)" != "$BASE" ||
       "$(git -C "$APP" branch --show-current)" != main ||
       -n "$(git -C "$APP" status --porcelain)" ]]; then rc=1; fi
 echo "RELEASE_769_INSTALLED_DEV=UNMODIFIED"
 echo "RELEASE_769_EXIT_STATUS=$rc"
 exit "$rc"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
git worktree add --detach "$QA" "$TARGET"
[[ "$(git -C "$QA" rev-parse HEAD)" == "$TARGET" ]] || fail "QA SHA mismatch"
export GIT_CONFIG_COUNT=2 GIT_CONFIG_KEY_0=safe.directory
export GIT_CONFIG_VALUE_0="$APP" GIT_CONFIG_KEY_1=safe.directory
export GIT_CONFIG_VALUE_1="$QA"
mkdir -m 700 "$RUN/data"
cd "$QA"
export TRACKER_DATA_DIR="$RUN/data" PYTHONPATH="$QA" PYTHONDONTWRITEBYTECODE=1
for script in scripts/tracker-qualify769.sh scripts/tracker-install769.sh scripts/tracker-release-scoped769.sh scripts/tracker-release.sh; do
 bash -n "$script"
done
"$PY" -B - <<'PYCODE'
import ast
from pathlib import Path
from jinja2 import Environment
src = (
 "app/main.py", "app/google_tasks_models769.py",
 "app/google_tasks_projection769.py", "app/google_tasks_client769.py",
 "app/google_tasks_sync769.py", "app/google_tasks_background769.py",
 "app/routers/google_tasks769.py", "tests/test_release769_google_tasks.py",
)
for name in src:
 ast.parse(Path(name).read_text(encoding="utf-8"), filename=name)
for name in ("app/templates/google_tasks769.html",
             "app/templates/regimen635.html", "app/templates/protocols.html"):
 Environment().parse(Path(name).read_text(encoding="utf-8"))
from app.google_tasks_models769 import (GoogleTasksConnection769, GoogleTasksList769,
 GoogleTasksLink769, GoogleTasksExclusion769)
expected = {"google_tasks_connection769","google_tasks_lists769",
            "google_tasks_links769","google_tasks_exclusions769"}
assert {x.__table__.name for x in (GoogleTasksConnection769, GoogleTasksList769,
                                   GoogleTasksLink769, GoogleTasksExclusion769)} == expected
print("RELEASE_769_SCHEMA_SYNTAX=PASSED")
PYCODE
"$PY" -B scripts/tracker-impact-preflight604.py --base "$BASE" --target "$TARGET" --root "$QA"
echo "RELEASE_769_IMPACT_PREFLIGHT=PASSED"
timeout 600 bash scripts/tracker-release-scoped769.sh "$PY"
echo "RELEASE_769_QUALIFICATION=PASSED_SCOPED_NO_DEPLOY"
