#!/usr/bin/env bash
# Release 768 exact-SHA, disposable DEV qualification. No installed-source or data writes.
set -Eeuo pipefail
umask 077
APP=/opt/tracker
PY="$APP/.venv/bin/python"
BASE=5d23aaf4f7e7fa4b54c1d5535a622bdd9e9aac13
REF=release/768-prod-relative-data-path-recovery
fail(){ echo "RELEASE_768_BLOCKED=$*" >&2; exit 1; }
[[ $# == 1 && "$1" =~ ^[0-9a-f]{40}$ ]] || fail "Exact candidate SHA required"
TARGET="$1"
[[ "$(id -u)" == 0 && "$(hostname -s)" == tracker-dev &&
 -n "$(printenv INVOCATION_ID || true)" ]] || fail "Root DEV systemd worker required"
[[ "$(readlink /proc/self/ns/net)" != "$(readlink /proc/1/ns/net)" ]] ||
 fail "PrivateNetwork=yes required"
[[ -x "$PY" && -d "$APP/.git" ]] || fail "Installed DEV missing"
cd "$APP"
export GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=safe.directory
export GIT_CONFIG_VALUE_0="$APP"
[[ "$(git branch --show-current)" == main &&
 "$(git rev-parse HEAD)" == "$BASE" &&
 -z "$(git status --porcelain)" ]] || fail "Clean Release 767 installed DEV base required"
systemctl is-active --quiet tracker.service || fail "DEV service inactive"
exec 9>/run/lock/tracker768-recovery-qa.lock
flock -n 9 || fail "Concurrent Release 768 qualification"
[[ "$(git rev-parse "refs/remotes/origin/$REF")" == "$TARGET" ]] ||
 fail "Release branch does not match pinned SHA"
git merge-base --is-ancestor "$BASE" "$TARGET" || fail "Non-descendant candidate"
git diff --check "$BASE" "$TARGET"
while IFS= read -r path; do
 case "$path" in
  scripts/tracker-prod-schema-backup767.py|\
  scripts/tracker_prod_remote568.sh|\
  scripts/tracker_promote568.py|\
  scripts/tracker-release-agent745.py|\
  scripts/tracker-recovery-bootstrap768.sh|\
  scripts/tracker-qualify768.sh|\
  scripts/tracker-install768.sh|\
  scripts/tracker-release-scoped768.sh|\
  docs/release-768-failed-prod-recovery.md|\
  tests/test_release768_recovery.py|\
  tests/test_release767_prod_schema_backup.py) ;;
  *) fail "Unreviewed release path: $path" ;;
 esac
done < <(git diff --name-only "$BASE" "$TARGET")
RUN="$(mktemp -d /tmp/tracker768-recovery-qa.XXXXXXXX)"
QA="$RUN/source"
cleanup(){
 local rc=$?
 trap - EXIT
 if [[ -d "$QA" ]] && ! git -C "$APP" worktree remove --force "$QA"; then rc=1; fi
 rm -rf -- "$RUN"
 if [[ "$(git -C "$APP" rev-parse HEAD)" != "$BASE" ||
       "$(git -C "$APP" branch --show-current)" != main ||
       -n "$(git -C "$APP" status --porcelain)" ]]; then rc=1; fi
 echo "RELEASE_768_INSTALLED_DEV=UNMODIFIED"
 echo "RELEASE_768_EXIT_STATUS=$rc"
 exit "$rc"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
git worktree add --detach "$QA" "$TARGET"
[[ "$(git -C "$QA" rev-parse HEAD)" == "$TARGET" ]] || fail "Detached QA SHA mismatch"
export GIT_CONFIG_COUNT=2 GIT_CONFIG_KEY_0=safe.directory
export GIT_CONFIG_VALUE_0="$APP" GIT_CONFIG_KEY_1=safe.directory
export GIT_CONFIG_VALUE_1="$QA"
mkdir -m 700 "$RUN/data"
cd "$QA"
export TRACKER_DATA_DIR="$RUN/data" PYTHONPATH="$QA" PYTHONDONTWRITEBYTECODE=1
for script in scripts/tracker-qualify768.sh scripts/tracker-install768.sh scripts/tracker-release-scoped768.sh scripts/tracker_prod_remote568.sh scripts/tracker-recovery-bootstrap768.sh scripts/tracker-release.sh; do
 bash -n "$script"
done
"$PY" -B - <<'PYCODE'
import ast
from pathlib import Path
files = (
    "scripts/tracker-prod-schema-backup767.py",
    "scripts/tracker_promote568.py",
    "scripts/tracker-release-agent745.py",
    "tests/test_release768_recovery.py",
    "tests/test_release767_prod_schema_backup.py",
)
for filename in files:
    ast.parse(Path(filename).read_text(encoding="utf-8"), filename=filename)
print("RELEASE_768_SYNTAX=PASSED")
PYCODE
"$PY" -B - <<'PYCODE'
from pathlib import Path
from jinja2 import Environment
remote = Path("scripts/tracker_prod_remote568.sh").read_text(encoding="utf-8")
guard = Path("scripts/tracker-prod-schema-backup768.py").read_text(encoding="utf-8")
assert "RELEASE_768_PROD_SCHEMA_BACKUP=PASSED" in remote
assert 'bash "$RUNNER"' in remote
assert "review_source" in guard and "verify_backup" in guard
assert "resolve_data_dir768" in guard
assert '[[ "$RELEASE" == 767 || "$RELEASE" == 768 ]]' in remote
print("RELEASE_768_PROD_GUARD_SYNTAX=PASSED")
PYCODE
"$PY" -B scripts/tracker-impact-preflight604.py --base "$BASE" --target "$TARGET" --root "$QA"
echo "RELEASE_768_IMPACT_PREFLIGHT=PASSED"
timeout 600 bash scripts/tracker-release-scoped768.sh "$PY"
echo "RELEASE_768_QUALIFICATION=PASSED_SCOPED_NO_DEPLOY"
