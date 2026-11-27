#!/usr/bin/env bash
# Release 806: exact-SHA, private, scoped comprehensive-optimization qualification. No installation.
set -Eeuo pipefail
umask 077
APP=/opt/tracker
PY="$APP/.venv/bin/python"
BASE=8f12563f1584f1812abe907d2b6f530e63674df8
REF=release/806-comprehensive-optimization
fail(){ echo "RELEASE_806_BLOCKED=$*" >&2; exit 1; }
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
 -z "$(git status --porcelain)" ]] || fail "Clean installed DEV 805 required"
systemctl is-active --quiet tracker.service || fail "DEV service inactive"
exec 9>/run/lock/tracker806-comprehensive-optimization-qa.lock
flock -n 9 || fail "Concurrent Release 806 qualification"
[[ "$(git rev-parse "refs/remotes/origin/$REF")" == "$TARGET" ]] ||
 fail "Release branch SHA changed"
git merge-base --is-ancestor "$BASE" "$TARGET" || fail "Non-descendant target"
git diff --check "$BASE" "$TARGET"
while IFS= read -r path; do
 case "$path" in
  app/static/release36_40.js|app/static/js/tracker-ux-3447-3452.js|app/static/core_workflow_97_104.js|app/templates/base.html|app/templates/inventory_health.html|tests/test_release762_progress.py|tests/test_release36_40_ui.py|tests/test_release635_regimen.py|tests/test_shared_optimization806.py|app/progress_calc762.py|app/routers/progress762.py|app/templates/progress762.html|docs/release-806-comprehensive-optimization.md|tests/test_progress_optimization806.py|scripts/tracker-benchmark806.py|scripts/tracker-install806.sh|scripts/tracker-qualify806.sh|scripts/tracker-release-scoped806.sh) ;;
  *) fail "Unreviewed changed path: $path";;
 esac
done < <(git diff --name-only "$BASE" "$TARGET")
[[ -z "$(git diff --name-only "$BASE" "$TARGET" -- app/models.py app/migrations.py app/db.py app/google_tasks_models769.py app/google_tasks_client769.py requirements.txt deploy/)" ]] ||
 fail "Unreviewed schema, OAuth or deployment change"
RUN="$(mktemp -d /tmp/tracker806-comprehensive-optimization.XXXXXXXX)"
QA="$RUN/source"
cleanup(){
 local rc=$?
 trap - EXIT
 if [[ -d "$QA" ]] && ! git -C "$APP" worktree remove --force "$QA"; then rc=1; fi
 rm -rf -- "$RUN"
 if [[ "$(git -C "$APP" rev-parse HEAD)" != "$BASE" ||
       "$(git -C "$APP" branch --show-current)" != main ||
       -n "$(git -C "$APP" status --porcelain)" ]]; then rc=1; fi
 echo "RELEASE_806_INSTALLED_DEV=UNMODIFIED"
 echo "RELEASE_806_EXIT_STATUS=$rc"
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
for file in scripts/tracker-qualify806.sh scripts/tracker-install806.sh scripts/tracker-release-scoped806.sh scripts/tracker-release.sh; do bash -n "$file"; done
"$PY" -B - <<'PYCODE'
import ast
from pathlib import Path
for path in ["app/progress_calc762.py", "app/routers/progress762.py", "tests/test_progress_optimization806.py", "tests/test_shared_optimization806.py", "tests/test_release36_40_ui.py", "tests/test_release635_regimen.py", "tests/test_release762_progress.py", "scripts/tracker-benchmark806.py"]:
 ast.parse(Path(path).read_text(encoding="utf-8"), filename=path)
print("RELEASE_806_SYNTAX=PASSED")
PYCODE
"$PY" -B scripts/tracker-impact-preflight604.py --base "$BASE" --target "$TARGET" --root "$QA"
echo "RELEASE_806_IMPACT_PREFLIGHT=PASSED"
"$PY" -B scripts/tracker-benchmark806.py
timeout 900 bash scripts/tracker-release-scoped806.sh "$PY"
echo "RELEASE_806_QUALIFICATION=PASSED_SCOPED_NO_DEPLOY"
