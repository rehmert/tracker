#!/usr/bin/env bash
# Release 668: DEV-scoped qualification and signed PROD deployment.
# GitHub is only a source repository. No hosted CI or GitHub deployment.
set -Eeuo pipefail
umask 077
APP=/opt/tracker
BRANCH=release/668-workout-completion
PY=/opt/tracker/.venv/bin/python
PROMOTER=/opt/tracker/scripts/tracker_promote568.py
die() { echo "RELEASE_668_ERROR=$*" >&2; exit 1; }
PHASE=all
if (( $# > 0 )); then PHASE="$1"; fi
[[ "$PHASE" == dev || "$PHASE" == promote || "$PHASE" == all ]] || die "Use dev, promote, all"
[[ "$(id -u)" == 0 && "$(hostname -s)" == tracker-dev ]] || die "Must be root on tracker-dev"
[[ -x "$PY" && -f "$PROMOTER" ]] || die "Missing DEV Python or promoter"
cd "$APP"
export GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=safe.directory GIT_CONFIG_VALUE_0="$APP"
[[ "$(git branch --show-current)" == main && -z "$(git status --porcelain)" ]] || die "Require clean main"
git fetch origin main "refs/heads/$BRANCH:refs/remotes/origin/$BRANCH"
TARGET="$(git rev-parse "refs/remotes/origin/$BRANCH")"
[[ "$TARGET" =~ ^[a-f0-9]{40}$ ]] || die "Invalid candidate SHA"
git merge-base --is-ancestor origin/main "$TARGET" || die "Candidate not descended from main"
if git diff --name-only origin/main "$TARGET" | grep -Eq '^(app/(db|models|migrations|workout_models[0-9]+)[.]py|alembic/|alembic.ini|requirements[^/]*|deploy/)'; then
  die "Migration/dependency/topology changes require separate reviewed qualification"
fi
if [[ "$PHASE" == dev || "$PHASE" == all ]]; then
  BASE="$(git rev-parse HEAD)"
  [[ "$(git rev-parse origin/main)" == "$BASE" ]] || die "DEV and origin/main baseline mismatch"
  PROD_BASE="$(ssh -o BatchMode=yes -o StrictHostKeyChecking=yes -n root@tracker-prod 'git -c safe.directory=/opt/tracker -C /opt/tracker rev-parse HEAD')"
  [[ "$PROD_BASE" == "$BASE" ]] || die "PROD is not at matching baseline; reconcile before deploying"
  STAGE="$(mktemp -d /tmp/tracker-668-runner.XXXXXXXX)"
  trap 'rm -rf -- "$STAGE"' EXIT
  git show "$TARGET:scripts/tracker-release.sh" > "$STAGE/runner.sh"
  EXPECTED="$(git rev-parse "$TARGET:scripts/tracker-release.sh")"
  [[ "$(git hash-object "$STAGE/runner.sh")" == "$EXPECTED" ]] || die "Pinned runner hash mismatch"
  bash -n "$STAGE/runner.sh"
  echo "RELEASE_668_DEV_BASE=$BASE"
  echo "RELEASE_668_TARGET=$TARGET"
  echo "RELEASE_668_TEST_MODE=FOCUSED_NO_FULL_SUITE"
  bash "$STAGE/runner.sh" --instance DEV --base "$BASE" --target "$TARGET" --ref "$BRANCH"
  [[ "$(git rev-parse HEAD)" == "$TARGET" ]] || die "DEV target not installed"
  systemctl is-active --quiet tracker || die "DEV service inactive"
  LOG=/etc/tracker-release/release-668-dev.log
  [[ -f "$LOG" && ! -L "$LOG" ]] || die "DEV qualification log unavailable"
  grep -Fxq "DEV_QUALIFIED_COMMIT=$TARGET" "$LOG" || die "Exact DEV qualification absent"
  grep -Fxq 'FOCUSED_RELEASE_GATE=PASSED' "$LOG" || die "Focused gate absent"
  grep -Fxq 'EXIT_STATUS=0' "$LOG" || die "DEV did not qualify"
  echo "RELEASE_668_DEV_QUALIFIED=$TARGET"
fi
if [[ "$PHASE" == promote || "$PHASE" == all ]]; then
  [[ "$(git rev-parse HEAD)" == "$TARGET" ]] || die "DEV is not at exact qualified target"
  PROD_BASE="$(ssh -o BatchMode=yes -o StrictHostKeyChecking=yes -n root@tracker-prod 'git -c safe.directory=/opt/tracker -C /opt/tracker rev-parse HEAD')"
  [[ "$PROD_BASE" =~ ^[a-f0-9]{40}$ ]] || die "Invalid PROD SHA"
  "$PY" "$PROMOTER" --release 668 --target "$TARGET" --prod-base "$PROD_BASE" --ref "$BRANCH"
  "$PY" "$PROMOTER" --release 668 --target "$TARGET" --prod-base "$PROD_BASE" --ref "$BRANCH" --execute
  echo "RELEASE_668_DEV_CONTROLLED_PROD=SUCCESS"
fi
