#!/usr/bin/env bash
# Release 773: exact-SHA isolated offline QA, never modifies installed DEV.
set -Eeuo pipefail
umask 077
APP=/opt/tracker
PY="$APP/.venv/bin/python"
BASE=47642b465b1cb98f40aab2ce68c6a7526394298d
REF=release/773-google-tasks-custom-titles
fail(){ echo "RELEASE_773_BLOCKED=$*" >&2; exit 1; }
[[ $# == 1 && "$1" =~ ^[0-9a-f]{40}$ ]] || fail "Exact pinned target required"
TARGET="$1"
[[ "$(id -u)" == 0 && "$(hostname -s)" == tracker-dev &&
 -n "$(printenv INVOCATION_ID || true)" ]] || fail "Root DEV systemd worker required"
[[ "$(readlink /proc/self/ns/net)" != "$(readlink /proc/1/ns/net)" ]] ||
 fail "PrivateNetwork=yes required"
[[ -d "$APP/.git" && -x "$PY" ]] || fail "Installed DEV checkout missing"
cd "$APP"
export GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=safe.directory GIT_CONFIG_VALUE_0="$APP"
[[ "$(git branch --show-current)" == main &&
 "$(git rev-parse HEAD)" == "$BASE" && -z "$(git status --porcelain)" ]] ||
 fail "Clean installed DEV Release 772 required"
systemctl is-active --quiet tracker.service || fail "DEV service inactive"
exec 9>/run/lock/tracker773-google-titles-qa.lock
flock -n 9 || fail "Concurrent Release 773 qualification"
[[ "$(git rev-parse "refs/remotes/origin/$REF")" == "$TARGET" ]] ||
 fail "Pinned target branch moved"
git merge-base --is-ancestor "$BASE" "$TARGET" || fail "Non-descendant release"
git diff --check "$BASE" "$TARGET"
while IFS= read -r path; do
 case "$path" in
  app/google_tasks_models769.py|\
  app/google_tasks_projection769.py|\
  app/routers/google_tasks769.py|\
  app/templates/google_tasks769.html|\
  scripts/tracker-prod-google-titles773.py|\
  scripts/tracker_prod_remote568.sh|\
  scripts/tracker-qualify773.sh|\
  scripts/tracker-install773.sh|\
  scripts/tracker-release-scoped773.sh|\
  tests/test_release773_google_custom_titles.py|\
  tests/test_release773_google_title_schema.py|\
  docs/release-773-google-tasks-custom-titles.md|\
  __never__) ;;
  *) fail "Unreviewed changed path: $path" ;;
 esac
done < <(git diff --name-only "$BASE" "$TARGET")
[[ -z "$(git diff --name-only "$BASE" "$TARGET" -- app/db.py app/models.py app/migrations.py app/main.py app/google_tasks_client769.py app/google_tasks_sync769.py requirements.txt deploy/ alembic/)" ]] ||
 fail "Unexpected core schema, OAuth, Google identity or deployment change"
RUN="$(mktemp -d /tmp/tracker773-google-titles-qa.XXXXXXXX)"
QA="$RUN/source"
cleanup(){
 local rc=$?
 trap - EXIT
 if [[ -d "$QA" ]] && ! git -C "$APP" worktree remove --force "$QA"; then rc=1; fi
 rm -rf -- "$RUN"
 if [[ "$(git -C "$APP" rev-parse HEAD)" != "$BASE" ||
       "$(git -C "$APP" branch --show-current)" != main ||
       -n "$(git -C "$APP" status --porcelain)" ]]; then rc=1; fi
 echo "RELEASE_773_INSTALLED_DEV=UNMODIFIED"
 echo "RELEASE_773_EXIT_STATUS=$rc"
 exit "$rc"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
git worktree add --detach "$QA" "$TARGET"
[[ "$(git -C "$QA" rev-parse HEAD)" == "$TARGET" ]] || fail "Isolated QA SHA mismatch"
export GIT_CONFIG_COUNT=2 GIT_CONFIG_KEY_0=safe.directory GIT_CONFIG_VALUE_0="$APP"
export GIT_CONFIG_KEY_1=safe.directory GIT_CONFIG_VALUE_1="$QA"
mkdir -m 700 "$RUN/data"
cd "$QA"
export TRACKER_DATA_DIR="$RUN/data" PYTHONPATH="$QA" PYTHONDONTWRITEBYTECODE=1
for script in scripts/tracker-qualify773.sh scripts/tracker-install773.sh scripts/tracker-release-scoped773.sh scripts/tracker_prod_remote568.sh scripts/tracker-release.sh; do bash -n "$script"; done
"$PY" -B - <<'PYCODE'
import ast
from pathlib import Path
from jinja2 import Environment
for path in ("app/google_tasks_models769.py","app/google_tasks_projection769.py",
             "app/routers/google_tasks769.py",
             "scripts/tracker-prod-google-titles773.py",
             "tests/test_release773_google_custom_titles.py",
             "tests/test_release773_google_title_schema.py"):
 ast.parse(Path(path).read_text(encoding="utf-8"), filename=path)
Environment().parse(Path("app/templates/google_tasks769.html").read_text(encoding="utf-8"))
print("RELEASE_773_SYNTAX=PASSED")
PYCODE
"$PY" -B scripts/tracker-impact-preflight604.py --base "$BASE" --target "$TARGET" --root "$QA"
echo "RELEASE_773_IMPACT_PREFLIGHT=PASSED"
timeout 600 bash scripts/tracker-release-scoped773.sh "$PY"
echo "RELEASE_773_QUALIFICATION=PASSED_SCOPED_NO_DEPLOY"
