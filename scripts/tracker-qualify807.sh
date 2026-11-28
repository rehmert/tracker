#!/usr/bin/env bash
# Release 807: exact-SHA, private, scoped integrated-wellness-anatomy qualification. No installation.
set -Eeuo pipefail
umask 077
APP=/opt/tracker
PY="$APP/.venv/bin/python"
BASE=2d597a9907ab3c7e1915f073ed5cd5e898e93b90
REF=release/807-integrated-wellness-anatomy
fail(){ echo "RELEASE_807_BLOCKED=$*" >&2; exit 1; }
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
 -z "$(git status --porcelain)" ]] || fail "Clean installed DEV 806 required"
systemctl is-active --quiet tracker.service || fail "DEV service inactive"
exec 9>/run/lock/tracker807-integrated-wellness-anatomy-qa.lock
flock -n 9 || fail "Concurrent Release 807 qualification"
[[ "$(git rev-parse "refs/remotes/origin/$REF")" == "$TARGET" ]] ||
 fail "Release branch SHA changed"
git merge-base --is-ancestor "$BASE" "$TARGET" || fail "Non-descendant target"
git diff --check "$BASE" "$TARGET"
while IFS= read -r path; do
 case "$path" in
  app/anatomical_sites807.py|app/health_analytics807.py|app/main.py|app/progress_goals807.py|app/routers/doses.py|app/routers/health_insights.py|app/routers/mobile509.py|app/routers/progress762.py|app/routers/protocols.py|app/routers/regimen635.py|app/routers/wellness807.py|app/secondary_preview430.py|app/site_history807.py|app/static/anatomy807.svg|app/static/css/tracker-anatomy807.css|app/static/css/tracker-report807.css|app/static/css/tracker-wellness807.css|app/static/js/tracker-anatomy807.js|app/static/js/tracker-report807.js|app/templates/_health_insights807.html|app/templates/_health_report807.html|app/templates/_injectable_fields807.html|app/templates/_regimen_today790.html|app/templates/_rotation807.html|app/templates/_site_reactions807.html|app/templates/_wellness807.html|app/templates/base.html|app/templates/blend_dose_edit711.html|app/templates/calendar_quick_dose786.html|app/templates/dose_edit.html|app/templates/doses.html|app/templates/health_insights.html|app/templates/mobile_today509.html|app/templates/physician807.html|app/templates/progress762.html|app/templates/protocols.html|app/templates/regimen635.html|app/templates/regimen_reactions807.html|app/templating.py|app/wellness807.py|app/wellness_models807.py|scripts/tracker-browser-qualify.sh|scripts/tracker-release.sh|scripts/tracker-schema-review807.py|tests/browser/test_anatomy807.py|tests/test_release807_wellness.py|scripts/tracker-qualify807.sh|scripts/tracker-install807.sh|scripts/tracker-release-scoped807.sh|scripts/tracker-benchmark807.py|docs/release-807-integrated-wellness-anatomy.md ;;
  *) fail "Unreviewed changed path: $path";;
 esac
done < <(git diff --name-only "$BASE" "$TARGET")
[[ -z "$(git diff --name-only "$BASE" "$TARGET" -- app/models.py app/migrations.py app/db.py app/google_tasks_models769.py app/google_tasks_client769.py requirements.txt deploy/)" ]] ||
 fail "Unreviewed schema, OAuth or deployment change"
RUN="$(mktemp -d /tmp/tracker807-integrated-wellness-anatomy.XXXXXXXX)"
QA="$RUN/source"
cleanup(){
 local rc=$?
 trap - EXIT
 if [[ -d "$QA" ]] && ! git -C "$APP" worktree remove --force "$QA"; then rc=1; fi
 rm -rf -- "$RUN"
 if [[ "$(git -C "$APP" rev-parse HEAD)" != "$BASE" ||
       "$(git -C "$APP" branch --show-current)" != main ||
       -n "$(git -C "$APP" status --porcelain)" ]]; then rc=1; fi
 echo "RELEASE_807_INSTALLED_DEV=UNMODIFIED"
 echo "RELEASE_807_EXIT_STATUS=$rc"
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
for file in scripts/tracker-qualify807.sh scripts/tracker-install807.sh scripts/tracker-release-scoped807.sh scripts/tracker-release.sh; do bash -n "$file"; done
"$PY" -B - <<'PYCODE'
import ast
from pathlib import Path
from subprocess import check_output
from xml.etree import ElementTree
from jinja2 import Environment
import os
for path in check_output(["git","diff","--name-only","2d597a9907ab3c7e1915f073ed5cd5e898e93b90","HEAD"],text=True).splitlines():
 if path.endswith(".py"):
  ast.parse(Path(path).read_text(encoding="utf-8"), filename=path)
 if path.endswith(".html"):
  from app.templating import templates
  templates.env.parse(Path(path).read_text(encoding="utf-8"))
 if path.endswith(".svg"):
  ElementTree.parse(path)
import app.main
print("RELEASE_807_SYNTAX=PASSED")
PYCODE
"$PY" -B scripts/tracker-impact-preflight604.py --base "$BASE" --target "$TARGET" --root "$QA"
echo "RELEASE_807_IMPACT_PREFLIGHT=PASSED"
node --check app/static/js/tracker-anatomy807.js
node --check app/static/js/tracker-report807.js
"$PY" -B scripts/tracker-schema-review807.py --root "$QA" --base "$BASE" --target "$TARGET"
"$PY" -B scripts/tracker-benchmark807.py
timeout 900 bash scripts/tracker-release-scoped807.sh "$PY"
echo "RELEASE_807_QUALIFICATION=PASSED_SCOPED_NO_DEPLOY"
