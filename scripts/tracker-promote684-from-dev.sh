#!/usr/bin/env bash
# Release 684: guarded DEV-controlled promotion of 679-684 to PROD.
# Invoke only from an isolated child shell on tracker-dev as root.
set -Eeuo pipefail
umask 077
APP=/opt/tracker
PY="$APP/.venv/bin/python"
BASE=b0a40f02837b6221b9d9474bdc74ac6a7c7835b0
TARGET=b42b39cb9f490325358a9a7ddc305ac7ca6ed5fb
REF=release/684-reconstitution-vial-picker-visible
fail(){ echo "RELEASE_684_PROMOTION_ERROR=$*" >&2; exit 1; }
[[ "$(id -u)" == 0 && "$(hostname -s)" == tracker-dev ]] || fail "Run as root on tracker-dev"
[[ -x "$PY" ]] || fail "Tracker Python unavailable"
cd "$APP"
export GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=safe.directory GIT_CONFIG_VALUE_0="$APP"
[[ "$(git branch --show-current)" == main && -z "$(git status --porcelain)" ]] || fail "Require clean installed DEV main checkout"
[[ "$(git rev-parse HEAD)" == "$TARGET" ]] || fail "DEV is not the approved Release 684"
systemctl is-active --quiet tracker || fail "DEV Tracker service inactive"
[[ -f /etc/tracker-release/release-684-dev.log && ! -L /etc/tracker-release/release-684-dev.log ]] || fail "DEV qualification receipt missing"
git fetch origin main "refs/heads/$REF:refs/remotes/origin/$REF"
[[ "$(git rev-parse origin/main)" == "$BASE" ]] || fail "GitHub main is not the expected PROD Release 678 baseline"
[[ "$(git rev-parse "refs/remotes/origin/$REF")" == "$TARGET" ]] || fail "Qualified release branch moved"
git merge-base --is-ancestor "$BASE" "$TARGET" || fail "Release 684 is not a fast-forward of PROD 678"
echo "PROD_PROMOTION_BASE=$BASE"
echo "PROD_PROMOTION_TARGET=$TARGET"
echo "PROD_PROMOTION_TEST_SCOPE=RELEASES_679_TO_684_FOCUSED_NO_FULL_SUITE"

# Existing signed promoter performs a read-only DEV/PROD cross-host preflight.
"$PY" "$APP/scripts/tracker_promote568.py" \
 --release 684 --target "$TARGET" --prod-base "$BASE" --ref "$REF"

STAGE="$(mktemp -d /tmp/tracker-684-prod-qualify.XXXXXXXX)"
QA="$STAGE/source"
cleanup(){
 code=$?
 trap - EXIT
 if [[ -d "$QA" ]]; then
   git -C "$APP" worktree remove --force "$QA" >/dev/null 2>&1 || true
 fi
 rm -rf -- "$STAGE"
 echo "RELEASE_684_PROMOTION_WRAPPER_EXIT_STATUS=$code"
 exit "$code"
}
trap cleanup EXIT
git worktree add --detach "$QA" "$TARGET"
export GIT_CONFIG_COUNT=2 GIT_CONFIG_KEY_0=safe.directory GIT_CONFIG_VALUE_0="$APP" GIT_CONFIG_KEY_1=safe.directory GIT_CONFIG_VALUE_1="$QA"
cd "$QA"
git diff --check "$BASE" "$TARGET"
"$PY" scripts/tracker-impact-preflight604.py --base "$BASE" --target "$TARGET" --root "$QA"
echo "CUMULATIVE_678_TO_684_STATIC_IMPACT=PASSED"
for number in 679 680 681 682 683 684; do
  gate="scripts/tracker-release-scoped${number}.sh"
  [[ -f "$gate" && ! -L "$gate" ]] || fail "Missing focused gate $gate"
  mkdir -p "$STAGE/test-data-${number}"
  export TRACKER_DATA_DIR="$STAGE/test-data-${number}" PYTHONPATH="$QA"
  echo "=== CUMULATIVE FOCUSED RELEASE ${number} ==="
  timeout 600 bash "$gate" "$PY"
  echo "CUMULATIVE_RELEASE_${number}_QUALIFICATION=PASSED"
done
unset TRACKER_DATA_DIR PYTHONPATH
cd "$APP"
[[ "$(git rev-parse HEAD)" == "$TARGET" && -z "$(git status --porcelain)" ]] || fail "DEV changed during isolated qualification"
echo "CUMULATIVE_679_TO_684_QUALIFICATION=PASSED"
# Remove isolated worktree before privileged signed promotion.
git worktree remove --force "$QA"
rm -rf -- "$STAGE"
trap - EXIT

# Explicitly authorized by operator: promote GitHub main, sign exact DEV
# qualification, and remotely deploy only via pre-existing trusted promoter.
"$PY" "$APP/scripts/tracker_promote568.py" \
 --release 684 --target "$TARGET" --prod-base "$BASE" --ref "$REF" --execute
echo "RELEASE_684_DEV_CONTROLLED_PROD=SUCCESS"
