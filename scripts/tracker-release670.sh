#!/usr/bin/env bash
# Release 670: code-only saved-food editor, DEV-qualified signed PROD promotion.
set -Eeuo pipefail
umask 077
APP=/opt/tracker
BRANCH=release/670-food-edit-action-button
PY=/opt/tracker/.venv/bin/python
PROMOTER=/opt/tracker/scripts/tracker_promote568.py
BASE670=b69aafdbb25348bbe8ed290b79ba242887e94e86
die() { echo "RELEASE_670_ERROR=$*" >&2; exit 1; }
PHASE="${1:-all}"
[[ "$PHASE" == dev || "$PHASE" == promote || "$PHASE" == all ]] ||
  die "Use dev, promote, or all"
[[ "$(id -u)" == 0 && "$(hostname -s)" == tracker-dev ]] ||
  die "Must run as root on tracker-dev"
[[ -x "$PY" && -f "$PROMOTER" ]] || die "Missing DEV Python or promoter"
cd "$APP"
export GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=safe.directory GIT_CONFIG_VALUE_0="$APP"
[[ "$(git branch --show-current)" == main && -z "$(git status --porcelain)" ]] ||
  die "Require clean main checkout"
git fetch origin main "refs/heads/$BRANCH:refs/remotes/origin/$BRANCH"
TARGET="$(git rev-parse "refs/remotes/origin/$BRANCH")"
[[ "$TARGET" =~ ^[0-9a-f]{40}$ ]] || die "Invalid candidate commit"
git merge-base --is-ancestor "$BASE670" "$TARGET" ||
  die "Candidate is not descended from reviewed PROD baseline"
REVIEWED="$(git show "$TARGET:docs/release-670-ready.txt" 2>/dev/null || true)"
[[ "$REVIEWED" == 'RELEASE_670_IMPLEMENTATION_REVIEWED=YES' ]] ||
  die "Release 670 source not yet qualified and reviewed"
if git diff --name-only "$BASE670" "$TARGET" |
  grep -Eq '^(app/(db|models|migrations|scoped_db|auth|security|csrf|session_auth|food_storage_guard)|alembic/|requirements[^/]*|deploy/)'; then
  die "Code-only release must not modify schema/security/dependencies"
fi
if [[ "$PHASE" == dev || "$PHASE" == all ]]; then
  BASE="$(git rev-parse HEAD)"
  [[ "$(git rev-parse origin/main)" == "$BASE" && "$BASE" == "$BASE670" ]] ||
    die "DEV installed baseline does not match reviewed main"
  PROD_BASE="$(ssh -o BatchMode=yes -o StrictHostKeyChecking=yes -n root@tracker-prod 'git -c safe.directory=/opt/tracker -C /opt/tracker rev-parse HEAD')"
  [[ "$PROD_BASE" == "$BASE" ]] ||
    die "PROD baseline does not match DEV"
  STAGE="$(mktemp -d /tmp/tracker-670-runner.XXXXXXXX)"
  trap 'rm -rf -- "$STAGE"' EXIT
  git show "$TARGET:scripts/tracker-release.sh" > "$STAGE/runner.sh"
  EXPECTED="$(git rev-parse "$TARGET:scripts/tracker-release.sh")"
  [[ "$(git hash-object "$STAGE/runner.sh")" == "$EXPECTED" ]] ||
    die "Pinned runner blob mismatch"
  bash -n "$STAGE/runner.sh"
  echo "RELEASE_670_DEV_BASE=$BASE"
  echo "RELEASE_670_TARGET=$TARGET"
  echo "RELEASE_670_TEST_MODE=FOCUSED_NO_FULL_SUITE"
  bash "$STAGE/runner.sh" --instance DEV --base "$BASE" --target "$TARGET" --ref "$BRANCH"
  [[ "$(git rev-parse HEAD)" == "$TARGET" ]] || die "DEV target not installed"
  systemctl is-active --quiet tracker || die "DEV service inactive"
  LOG=/etc/tracker-release/release-670-dev.log
  [[ -f "$LOG" && ! -L "$LOG" ]] || die "DEV qualification receipt unavailable"
  grep -Fxq "DEV_QUALIFIED_COMMIT=$TARGET" "$LOG" || die "Exact DEV receipt mismatch"
  grep -Fxq "FOCUSED_RELEASE_GATE=PASSED" "$LOG" || die "Focused regression gate missing"
  grep -Fxq "EXIT_STATUS=0" "$LOG" || die "DEV qualification not successful"
  echo "RELEASE_670_DEV_QUALIFIED=$TARGET"
fi
if [[ "$PHASE" == promote || "$PHASE" == all ]]; then
  [[ "$(git rev-parse HEAD)" == "$TARGET" ]] ||
    die "DEV not running exact candidate"
  PROD_BASE="$(ssh -o BatchMode=yes -o StrictHostKeyChecking=yes -n root@tracker-prod 'git -c safe.directory=/opt/tracker -C /opt/tracker rev-parse HEAD')"
  [[ "$PROD_BASE" == "$BASE670" ]] || die "Unexpected PROD baseline"
  "$PY" "$PROMOTER" --release 670 --target "$TARGET" --prod-base "$PROD_BASE" --ref "$BRANCH"
  "$PY" "$PROMOTER" --release 670 --target "$TARGET" --prod-base "$PROD_BASE" --ref "$BRANCH" --execute
  echo "RELEASE_670_DEV_CONTROLLED_PROD=SUCCESS"
fi
