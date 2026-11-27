#!/usr/bin/env bash
# Release 798: exact-SHA, private, daily and calendar performance qualification. No installation.
set -Eeuo pipefail
umask 077
APP=/opt/tracker
PY="$APP/.venv/bin/python"
BASE=5d52af77cdccfdfe02248f59662f1ee37e6227ce
REF=release/798-frontend-performance
fail(){ echo "RELEASE_798_BLOCKED=$*" >&2; exit 1; }
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
 -z "$(git status --porcelain)" ]] || fail "Clean installed DEV 797 required"
systemctl is-active --quiet tracker.service || fail "DEV service inactive"
exec 9>/run/lock/tracker798-frontend-performance-qa.lock
flock -n 9 || fail "Concurrent Release 798 qualification"
[[ "$(git rev-parse "refs/remotes/origin/$REF")" == "$TARGET" ]] ||
 fail "Release branch SHA changed"
git merge-base --is-ancestor "$BASE" "$TARGET" || fail "Non-descendant target"
git diff --check "$BASE" "$TARGET"
while IFS= read -r path; do
 case "$path" in
  app/templates/base.html|app/static/js/tracker-section-explanations598.js|app/static/js/tracker-page-title-case.js|tests/test_frontend_performance798.py|tests/test_release764_compound_title_case.py|tests/test_explanation_touch680.py|tests/test_release598_dashboard_density.py|scripts/tracker-qualify798.sh|scripts/tracker-install798.sh|scripts/tracker-release-scoped798.sh) ;;
  *) fail "Unreviewed changed path: $path";;
 esac
done < <(git diff --name-only "$BASE" "$TARGET")
[[ -z "$(git diff --name-only "$BASE" "$TARGET" -- app/models.py app/migrations.py app/db.py app/google_tasks_models769.py app/google_tasks_client769.py requirements.txt deploy/)" ]] ||
 fail "Unreviewed schema, OAuth or deployment change"
RUN="$(mktemp -d /tmp/tracker798-frontend-performance.XXXXXXXX)"
QA="$RUN/source"
cleanup(){
 local rc=$?
 trap - EXIT
 if [[ -d "$QA" ]] && ! git -C "$APP" worktree remove --force "$QA"; then rc=1; fi
 rm -rf -- "$RUN"
 if [[ "$(git -C "$APP" rev-parse HEAD)" != "$BASE" ||
       "$(git -C "$APP" branch --show-current)" != main ||
       -n "$(git -C "$APP" status --porcelain)" ]]; then rc=1; fi
 echo "RELEASE_798_INSTALLED_DEV=UNMODIFIED"
 echo "RELEASE_798_EXIT_STATUS=$rc"
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
for file in scripts/tracker-qualify798.sh scripts/tracker-install798.sh scripts/tracker-release-scoped798.sh scripts/tracker-release.sh; do bash -n "$file"; done
"$PY" -B - <<'PYCODE'
import ast
from pathlib import Path
from jinja2 import Environment
Environment().parse(Path("app/templates/base.html").read_text(encoding="utf-8"))
for path in ("tests/test_frontend_performance798.py",):
 ast.parse(Path(path).read_text(encoding="utf-8"), filename=path)
print("RELEASE_798_SYNTAX=PASSED")
PYCODE
"$PY" -B scripts/tracker-impact-preflight604.py --base "$BASE" --target "$TARGET" --root "$QA"
echo "RELEASE_798_IMPACT_PREFLIGHT=PASSED"
timeout 600 bash scripts/tracker-release-scoped798.sh "$PY"
echo "RELEASE_798_QUALIFICATION=PASSED_SCOPED_NO_DEPLOY"
