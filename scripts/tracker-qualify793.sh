#!/usr/bin/env bash
# Release 793: exact-SHA, private, unified visual design and navigation qualification. No installation.
set -Eeuo pipefail
umask 077
APP=/opt/tracker
PY="$APP/.venv/bin/python"
BASE=9f79787956726e105d55906483b7e851db5106fa
REF=release/793-design-system
fail(){ echo "RELEASE_793_BLOCKED=$*" >&2; exit 1; }
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
 -z "$(git status --porcelain)" ]] || fail "Clean installed DEV 792 required"
systemctl is-active --quiet tracker.service || fail "DEV service inactive"
exec 9>/run/lock/tracker793-design-system-qa.lock
flock -n 9 || fail "Concurrent Release 793 qualification"
[[ "$(git rev-parse "refs/remotes/origin/$REF")" == "$TARGET" ]] ||
 fail "Release branch SHA changed"
git merge-base --is-ancestor "$BASE" "$TARGET" || fail "Non-descendant target"
git diff --check "$BASE" "$TARGET"
while IFS= read -r path; do
 case "$path" in
  AGENTS.md|\
  app/navigation.py|\
  app/routers/workflow_hub.py|\
  app/static/css/tracker-design-system793.css|\
  app/static/css/tracker-server-theme-default510.css|\
  app/static/tracker_focus.js|\
  app/templates/base.html|\
  app/templating.py|\
  tests/test_design_system793.py|\
  tests/test_headings531.py|\
  tests/test_nav_titlecase.py|\
  tests/test_navigation_focus.py|\
  tests/test_navigation_productivity.py|\
  tests/test_release775_google_tasks_navigation.py|\
  tests/test_release776_google_tasks_focus.py|\
  tests/test_server_theme510.py|\
  scripts/tracker-qualify793.sh|\
  scripts/tracker-install793.sh|\
  scripts/tracker-release-scoped793.sh|\
  __never__) ;;
  *) fail "Unreviewed changed path: $path";;
 esac
done < <(git diff --name-only "$BASE" "$TARGET")
[[ -z "$(git diff --name-only "$BASE" "$TARGET" -- app/models.py app/migrations.py app/db.py app/google_tasks_models769.py app/google_tasks_client769.py requirements.txt deploy/)" ]] ||
 fail "Unreviewed schema, OAuth or deployment change"
RUN="$(mktemp -d /tmp/tracker793-design-system.XXXXXXXX)"
QA="$RUN/source"
cleanup(){
 local rc=$?
 trap - EXIT
 if [[ -d "$QA" ]] && ! git -C "$APP" worktree remove --force "$QA"; then rc=1; fi
 rm -rf -- "$RUN"
 if [[ "$(git -C "$APP" rev-parse HEAD)" != "$BASE" ||
       "$(git -C "$APP" branch --show-current)" != main ||
       -n "$(git -C "$APP" status --porcelain)" ]]; then rc=1; fi
 echo "RELEASE_793_INSTALLED_DEV=UNMODIFIED"
 echo "RELEASE_793_EXIT_STATUS=$rc"
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
for file in scripts/tracker-qualify793.sh scripts/tracker-install793.sh scripts/tracker-release-scoped793.sh scripts/tracker-release.sh; do bash -n "$file"; done
"$PY" -B - <<'PYCODE'
import ast
from pathlib import Path
from jinja2 import Environment
for path in ("app/navigation.py", "app/routers/workflow_hub.py", "app/templating.py", "tests/test_design_system793.py", "tests/test_headings531.py", "tests/test_nav_titlecase.py", "tests/test_navigation_focus.py", "tests/test_navigation_productivity.py", "tests/test_release775_google_tasks_navigation.py", "tests/test_release776_google_tasks_focus.py", "tests/test_server_theme510.py",):
 ast.parse(Path(path).read_text(encoding="utf-8"), filename=path)
for path in ("app/templates/base.html",):
 Environment().parse(Path(path).read_text(encoding="utf-8"))
print("RELEASE_793_SYNTAX=PASSED")
PYCODE
"$PY" -B scripts/tracker-impact-preflight604.py --base "$BASE" --target "$TARGET" --root "$QA"
echo "RELEASE_793_IMPACT_PREFLIGHT=PASSED"
timeout 600 bash scripts/tracker-release-scoped793.sh "$PY"
echo "RELEASE_793_QUALIFICATION=PASSED_SCOPED_NO_DEPLOY"
