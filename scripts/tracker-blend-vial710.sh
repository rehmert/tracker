#!/usr/bin/env bash
# Release 710: DEV-only isolated qualification of unified physical vial
# dose logging. The GitHub commit is pinned by the invoking SSH wrapper;
# this worker cannot deploy DEV/PROD or edit live data.
set -Eeuo pipefail
umask 077
APP=/opt/tracker
PY="$APP/.venv/bin/python"
BASE=4c084ade9063b3b01c2de0a4a055d2e23470b2a3
REF=release/710-unified-blend-vial-dosing
fail() { echo "RELEASE_710_BLOCKED=$*" >&2; exit 1; }

[[ "$#" == 1 && "$1" =~ ^[0-9a-f]{40}$ ]] ||
  fail "Expected exact immutable candidate SHA"
TARGET="$1"
[[ "$(id -u)" == 0 && "$(hostname -s)" == tracker-dev &&
   -n "${INVOCATION_ID:-}" ]] ||
  fail "Root systemd worker on tracker-dev required"
[[ "$(readlink /proc/self/ns/net)" != "$(readlink /proc/1/ns/net)" ]] ||
  fail "PrivateNetwork=yes required"
[[ -x "$PY" && -d "$APP/.git" ]] ||
  fail "Installed DEV source/Python missing"

cd "$APP"
export GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=safe.directory
export GIT_CONFIG_VALUE_0="$APP"
[[ "$(git branch --show-current)" == main &&
   "$(git rev-parse HEAD)" == "$BASE" &&
   -z "$(git status --porcelain)" ]] ||
  fail "Clean installed Release 705 required"
systemctl is-active --quiet tracker || fail "Installed DEV service inactive"
exec 9>/run/lock/tracker710-blend-vial.lock
flock -n 9 || fail "Another Release 710 run active"
[[ "$(git rev-parse "refs/remotes/origin/$REF")" == "$TARGET" ]] ||
  fail "Fetched ref does not match approved SHA"
git merge-base --is-ancestor "$BASE" "$TARGET" ||
  fail "Candidate ancestry invalid"
git diff --check "$BASE" "$TARGET"

# No application-wide unrelated changes, requirements, or installed data.
while IFS= read -r path; do
  case "$path" in
    app/blend_dose_unified710.py|\
    app/manual_supplies.py|\
    app/migrations.py|\
    app/models.py|\
    app/routers/doses.py|\
    app/static/dose_context.js|\
    app/static/js/tracker-dose-fast602.js|\
    app/static/js/tracker-dose-source710.js|\
    app/templates/_blend_dose_preview710.html|\
    app/templates/base.html|\
    app/templates/blend_detail.html|\
    app/templates/doses.html|\
    docs/release-710-unified-blend-dosing.md|\
    scripts/tracker-blend-vial710.sh|\
    scripts/tracker-browser-qualify.sh|\
    scripts/tracker-install710.sh|\
    scripts/tracker-release-scoped710.sh|\
    scripts/tracker-release.sh|\
    scripts/tracker_prod_remote568.sh|\
    scripts/tracker_schema_review710.py|\
    tests/browser/test_blend_unified_dose710.py|\
    tests/test_browser_qualification511.py|\
    tests/test_release564_blend_dose_selector.py|\
    tests/test_release611_blend_calendar.py|\
    tests/test_release602_mobile_bundle.py|\
    tests/test_release710_unified_blend_dose.py|\
    tests/test_release710_unified_source.py) ;;
    *) fail "Unexpected Release 710 source path: $path" ;;
  esac
done < <(git diff --name-only "$BASE" "$TARGET")

RUN="$(mktemp -d /tmp/tracker710-blend-vial.XXXXXXXX)"
QA="$RUN/source"
cleanup() {
  local status=$?
  trap - EXIT
  if [[ -d "$QA" ]] &&
     ! git -C "$APP" worktree remove --force "$QA"; then
    echo "RELEASE_710_BLOCKED=Source worktree cleanup failed" >&2
    status=1
  fi
  rm -rf -- "$RUN"
  if [[ "$(git -C "$APP" rev-parse HEAD)" != "$BASE" ||
       "$(git -C "$APP" branch --show-current)" != main ||
       -n "$(git -C "$APP" status --porcelain)" ]]; then
    echo "RELEASE_710_BLOCKED=Installed DEV changed" >&2
    status=1
  fi
  echo "RELEASE_710_INSTALLED_DEV=UNMODIFIED"
  echo "RELEASE_710_EXIT_STATUS=$status"
  exit "$status"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

git worktree add --detach "$QA" "$TARGET"
[[ "$(git -C "$QA" rev-parse HEAD)" == "$TARGET" ]] ||
  fail "QA worktree commit mismatch"
export GIT_CONFIG_COUNT=2
export GIT_CONFIG_KEY_0=safe.directory
export GIT_CONFIG_VALUE_0="$APP"
export GIT_CONFIG_KEY_1=safe.directory
export GIT_CONFIG_VALUE_1="$QA"
mkdir -m 700 "$RUN/data"
cd "$QA"
export PYTHONPATH="$QA" TRACKER_DATA_DIR="$RUN/data"
export PYTHONDONTWRITEBYTECODE=1

"$PY" -B scripts/tracker-impact-preflight604.py \
    --base "$BASE" --target "$TARGET" --root "$QA"
echo "RELEASE_710_ASSET_IMPACT_PREFLIGHT=PASSED"

bash -n scripts/tracker-blend-vial710.sh
bash -n scripts/tracker-browser-qualify.sh
bash -n scripts/tracker-release.sh
bash -n scripts/tracker_prod_remote568.sh
bash -n scripts/tracker-install710.sh
bash -n scripts/tracker-release-scoped710.sh
"$PY" -B scripts/tracker_schema_review710.py --root "$APP" --base "$BASE" --target "$TARGET"
"$PY" -B -m compileall -q app/blend_dose_unified710.py \
    app/models.py app/migrations.py app/manual_supplies.py \
    app/routers/doses.py
"$PY" -B -m pytest -q --tb=short --maxfail=1 \
    tests/test_release710_unified_source.py \
    tests/test_release602_mobile_bundle.py::test_602_dose_draft_fastpath_and_original_form \
    tests/test_release710_unified_blend_dose.py \
    tests/test_release564_blend_dose_selector.py \
    tests/test_blends.py \
    tests/test_release611_blend_calendar.py \
    tests/test_stage17_dose_blend_integrity.py \
    tests/test_dose_final_review.py \
    tests/test_dose_disposable_review.py \
    tests/test_dose_sequential_workflow.py \
    tests/test_dose_transaction_cleanup.py \
    tests/test_dose_unit_aware_supply_inputs.py \
    tests/test_dose_correction_net_inventory.py \
    tests/test_browser_qualification511.py::test_511_every_browser_module_in_disposable_qualification
echo "RELEASE_710_SOURCE=PASSED"
echo "RELEASE_710_SCOPED_BACKEND=PASSED"

# One strict-CSRF signed production-shaped browser lifecycle over both
# HTTP and HTTPS; actual browser source and SQLite data are disposable.
bash scripts/tracker-browser-qualify.sh "$QA" "$PY" \
    --targeted-strict blend-vial710

echo "RELEASE_710_UNIFIED_BLEND_BROWSER=PASSED"
echo "RELEASE_710_SCOPE=TARGETED_NOT_FULL_RELEASE"
echo "RELEASE_710_GLOBAL_CSRF=UNCHANGED"
echo "RELEASE_710_DEPLOYMENT=NONE_DEV_AND_PROD_UNTOUCHED"
