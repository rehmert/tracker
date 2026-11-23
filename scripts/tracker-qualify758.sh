#!/usr/bin/env bash
# Release 758 exact-SHA, disposable DEV qualification. No installed-source or data writes.
set -Eeuo pipefail
umask 077
APP=/opt/tracker
PY="$APP/.venv/bin/python"
BASE=90b297fc07c950d5a44a0bf8fe7d4beabfd8b30f
REF=release/758-vial-label-dose-markings
fail(){ echo "RELEASE_758_BLOCKED=$*" >&2; exit 1; }
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
 -z "$(git status --porcelain)" ]] || fail "Clean Release 757 installed DEV base required"
systemctl is-active --quiet tracker.service || fail "DEV service inactive"
exec 9>/run/lock/tracker758-label-qa.lock
flock -n 9 || fail "Concurrent Release 758 qualification"
[[ "$(git rev-parse "refs/remotes/origin/$REF")" == "$TARGET" ]] ||
 fail "Release branch does not match pinned SHA"
git merge-base --is-ancestor "$BASE" "$TARGET" || fail "Non-descendant candidate"
git diff --check "$BASE" "$TARGET"
while IFS= read -r path; do
 case "$path" in
  app/migrations.py|\
  app/models.py|\
  app/routers/purchases.py|\
  app/routers/vials.py|\
  app/templates/purchase_detail.html|\
  app/templates/vial_detail.html|\
  app/templates/vial_label_sheets447.html|\
  app/templates/vial_labels423.html|\
  app/templates/vials.html|\
  app/vial_label_compact758.py|\
  app/vial_label_dose758.py|\
  app/vial_label_fourline758.py|\
  app/vial_label_sheets447.py|\
  app/vial_labels423.py|\
  docs/release-758-vial-label-dose-markings.md|\
  scripts/tracker-release-scoped758.sh|\
  scripts/tracker-qualify758.sh|\
  scripts/tracker-install758.sh|\
  tests/test_release758_vial_label_30x15.py|\
  tests/test_release758_vial_label_40x20.py|\
  tests/test_release758_vial_label_dose.py|\
  tests/test_release758_vial_label_fourline.py|\
  tests/test_release758_vial_production_date.py|\
  tests/test_vial_label_rotation431.py) ;;
  *) fail "Unreviewed release path: $path" ;;
 esac
done < <(git diff --name-only "$BASE" "$TARGET")
RUN="$(mktemp -d /tmp/tracker758-label-qa.XXXXXXXX)"
QA="$RUN/source"
cleanup(){
 local rc=$?
 trap - EXIT
 if [[ -d "$QA" ]] && ! git -C "$APP" worktree remove --force "$QA"; then rc=1; fi
 rm -rf -- "$RUN"
 if [[ "$(git -C "$APP" rev-parse HEAD)" != "$BASE" ||
       "$(git -C "$APP" branch --show-current)" != main ||
       -n "$(git -C "$APP" status --porcelain)" ]]; then rc=1; fi
 echo "RELEASE_758_INSTALLED_DEV=UNMODIFIED"
 echo "RELEASE_758_EXIT_STATUS=$rc"
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
for script in scripts/tracker-qualify758.sh scripts/tracker-install758.sh scripts/tracker-release-scoped758.sh; do
 bash -n "$script"
done
"$PY" -B - <<'PYCODE'
import ast
from pathlib import Path
files = (
    "app/vial_label_compact758.py",
    "app/vial_label_fourline758.py",
    "app/vial_label_dose758.py",
    "app/vial_labels423.py",
    "app/vial_label_sheets447.py",
    "app/routers/vials.py",
    "tests/test_release758_vial_label_40x20.py",
)
for filename in files:
    ast.parse(Path(filename).read_text(encoding="utf-8"), filename=filename)
print("RELEASE_758_SYNTAX=PASSED")
PYCODE
"$PY" -B scripts/tracker-impact-preflight604.py --base "$BASE" --target "$TARGET" --root "$QA"
echo "RELEASE_758_IMPACT_PREFLIGHT=PASSED"
timeout 600 bash scripts/tracker-release-scoped758.sh "$PY"
echo "RELEASE_758_QUALIFICATION=PASSED_SCOPED_NO_DEPLOY"
