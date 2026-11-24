#!/usr/bin/env bash
# Release 779: exact-SHA, private, Universal compact 24-hour entry qualification. No installation.
set -Eeuo pipefail
umask 077
APP=/opt/tracker
PY="$APP/.venv/bin/python"
BASE=666ee1076b77e723e414df208312ef51e123e635
REF=release/779-colon-free-24h-entry
fail(){ echo "RELEASE_779_BLOCKED=$*" >&2; exit 1; }
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
 -z "$(git status --porcelain)" ]] || fail "Clean installed DEV 778 required"
systemctl is-active --quiet tracker.service || fail "DEV service inactive"
exec 9>/run/lock/tracker779-compact-time-qa.lock
flock -n 9 || fail "Concurrent Release 779 qualification"
[[ "$(git rev-parse "refs/remotes/origin/$REF")" == "$TARGET" ]] ||
 fail "Release branch SHA changed"
git merge-base --is-ancestor "$BASE" "$TARGET" || fail "Non-descendant target"
git diff --check "$BASE" "$TARGET"
while IFS= read -r path; do
 case "$path" in
  app/static/js/tracker-time24-global713.js|\
  app/static/js/tracker-time24-371.js|\
  app/templates/base.html|\
  app/templates/doses.html|\
  app/templates/dose_edit.html|\
  app/templates/vitals.html|\
  app/templates/vitals_edit.html|\
  app/templates/blend_dose_edit711.html|\
  scripts/tracker-time24-check371.cjs|\
  scripts/tracker-time24-check779.cjs|\
  tests/test_release713_timeline_time24.py|\
  tests/test_release779_compact_time.py|\
  docs/release-779-compact-military-time.md|\
  docs/ux-time-entry.md|\
  scripts/tracker-qualify779.sh|\
  scripts/tracker-install779.sh|\
  scripts/tracker-release-scoped779.sh|\
  __never__) ;;
  *) fail "Unreviewed changed path: $path";;
 esac
done < <(git diff --name-only "$BASE" "$TARGET")
[[ -z "$(git diff --name-only "$BASE" "$TARGET" -- app/models.py app/migrations.py app/db.py app/google_tasks_models769.py app/google_tasks_client769.py app/google_tasks_sync769.py requirements.txt deploy/)" ]] ||
 fail "Unreviewed schema, OAuth or deployment change"
RUN="$(mktemp -d /tmp/tracker779-compact-time.XXXXXXXX)"
QA="$RUN/source"
cleanup(){
 local rc=$?
 trap - EXIT
 if [[ -d "$QA" ]] && ! git -C "$APP" worktree remove --force "$QA"; then rc=1; fi
 rm -rf -- "$RUN"
 if [[ "$(git -C "$APP" rev-parse HEAD)" != "$BASE" ||
       "$(git -C "$APP" branch --show-current)" != main ||
       -n "$(git -C "$APP" status --porcelain)" ]]; then rc=1; fi
 echo "RELEASE_779_INSTALLED_DEV=UNMODIFIED"
 echo "RELEASE_779_EXIT_STATUS=$rc"
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
for file in scripts/tracker-qualify779.sh scripts/tracker-install779.sh scripts/tracker-release-scoped779.sh scripts/tracker-release.sh; do bash -n "$file"; done
for file in app/static/js/tracker-time24-global713.js app/static/js/tracker-time24-371.js scripts/tracker-time24-check779.cjs scripts/tracker-time24-check371.cjs; do node --check "$file"; done
"$PY" -B - <<'PYCODE'
import ast
from pathlib import Path
from jinja2 import Environment
for path in ("tests/test_release779_compact_time.py",
             "tests/test_release713_timeline_time24.py"):
 ast.parse(Path(path).read_text(encoding="utf-8"), filename=path)
for path in ("app/templates/base.html", "app/templates/doses.html",
             "app/templates/dose_edit.html", "app/templates/vitals.html",
             "app/templates/vitals_edit.html", "app/templates/blend_dose_edit711.html"):
 Environment().parse(Path(path).read_text(encoding="utf-8"))
print("RELEASE_779_SYNTAX=PASSED")
PYCODE
"$PY" -B scripts/tracker-impact-preflight604.py --base "$BASE" --target "$TARGET" --root "$QA"
echo "RELEASE_779_IMPACT_PREFLIGHT=PASSED"
timeout 600 bash scripts/tracker-release-scoped779.sh "$PY"
echo "RELEASE_779_QUALIFICATION=PASSED_SCOPED_NO_DEPLOY"
