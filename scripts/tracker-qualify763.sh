#!/usr/bin/env bash
# Release 763 exact-SHA qualification; no live source/data modification.
set -Eeuo pipefail
umask 077
APP=/opt/tracker
PY="$APP/.venv/bin/python"
BASE=35f6aa42aac648f3ed5af527620bd5f4b702b486
REF=release/763-progress-prod-hardening
fail(){ echo "RELEASE_763_BLOCKED=$*" >&2; exit 1; }
[[ $# == 1 && "$1" =~ ^[0-9a-f]{40}$ ]] || fail "Exact target SHA required"
TARGET="$1"
[[ "$(id -u)" == 0 && "$(hostname -s)" == tracker-dev &&
 -n "$(printenv INVOCATION_ID || true)" ]] || fail "DEV systemd root worker required"
[[ "$(readlink /proc/self/ns/net)" != "$(readlink /proc/1/ns/net)" ]] ||
 fail "PrivateNetwork=yes required"
[[ -x "$PY" && -d "$APP/.git" ]] || fail "DEV installation missing"
cd "$APP"
export GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=safe.directory GIT_CONFIG_VALUE_0="$APP"
[[ "$(git branch --show-current)" == main &&
 "$(git rev-parse HEAD)" == "$BASE" &&
 -z "$(git status --porcelain)" ]] || fail "Clean DEV Release 762 baseline required"
systemctl is-active --quiet tracker.service || fail "DEV app service inactive"
exec 9>/run/lock/tracker763-progress-qa.lock
flock -n 9 || fail "Concurrent Release 763 QA"
[[ "$(git rev-parse "refs/remotes/origin/$REF")" == "$TARGET" ]] ||
 fail "Pinned release ref mismatch"
git merge-base --is-ancestor "$BASE" "$TARGET" || fail "Target is not descendant of DEV 762"
git diff --check "$BASE" "$TARGET"
while IFS= read -r path; do
 case "$path" in
  app/progress_calc762.py|app/routers/progress762.py|app/templates/progress762.html|\
  app/static/js/tracker-progress763.js|\
  scripts/tracker-release.sh|scripts/tracker_prod_remote568.sh|\
  scripts/tracker_schema_review763.py|scripts/tracker-qualify763.sh|\
  scripts/tracker-install763.sh|scripts/tracker-release-scoped763.sh|\
  tests/test_release762_progress.py|tests/browser/test_progress763.py|\
  docs/release-763-progress-prod-hardening.md) ;;
  *) fail "Unreviewed release path: $path";;
 esac
done < <(git diff --name-only "$BASE" "$TARGET")
RUN="$(mktemp -d /tmp/tracker763-progress-qa.XXXXXXXX)"
QA="$RUN/source"
cleanup(){
 local rc=$?
 trap - EXIT
 if [[ -d "$QA" ]] && ! git -C "$APP" worktree remove --force "$QA"; then rc=1; fi
 rm -rf -- "$RUN"
 [[ "$(git -C "$APP" rev-parse HEAD)" == "$BASE" &&
    "$(git -C "$APP" branch --show-current)" == main &&
    -z "$(git -C "$APP" status --porcelain)" ]] || rc=1
 echo "RELEASE_763_INSTALLED_DEV=UNMODIFIED"
 echo "RELEASE_763_EXIT_STATUS=$rc"
 exit "$rc"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
git worktree add --detach "$QA" "$TARGET"
[[ "$(git -C "$QA" rev-parse HEAD)" == "$TARGET" ]] || fail "QA checkout mismatch"
export GIT_CONFIG_COUNT=2 GIT_CONFIG_KEY_0=safe.directory
export GIT_CONFIG_VALUE_0="$APP" GIT_CONFIG_KEY_1=safe.directory
export GIT_CONFIG_VALUE_1="$QA"
mkdir -m 700 "$RUN/data"
cd "$QA"
export TRACKER_DATA_DIR="$RUN/data" PYTHONPATH="$QA" PYTHONDONTWRITEBYTECODE=1
for path in scripts/tracker-qualify763.sh scripts/tracker-install763.sh \
 scripts/tracker-release-scoped763.sh scripts/tracker-release.sh \
 scripts/tracker_prod_remote568.sh; do bash -n "$path"; done
node --check app/static/js/tracker-progress763.js
"$PY" -B - <<'PY'
import ast
from pathlib import Path
from jinja2 import Environment
for name in ("app/progress_calc762.py","app/routers/progress762.py",
             "scripts/tracker_schema_review763.py",
             "tests/test_release762_progress.py","tests/browser/test_progress763.py"):
    ast.parse(Path(name).read_text(encoding="utf-8"), filename=name)
Environment().parse(Path("app/templates/progress762.html").read_text(encoding="utf-8"))
print("RELEASE_763_SYNTAX=PASSED")
PY
"$PY" -B scripts/tracker_schema_review763.py --root "$QA" \
 --base 04fd141daa17fd2055f9177527296eb9165a59d2 --target "$TARGET"
"$PY" -B scripts/tracker-impact-preflight604.py --base "$BASE" --target "$TARGET" --root "$QA"
echo "RELEASE_763_IMPACT_PREFLIGHT=PASSED"
timeout 600 bash scripts/tracker-release-scoped763.sh "$PY"
echo "RELEASE_763_QUALIFICATION=PASSED_SCOPED_NO_DEPLOY"
