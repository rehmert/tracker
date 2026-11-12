#!/usr/bin/env bash
# Release 584: exact-commit DEV-only source/browser preflight. Never deploys.
set -Eeuo pipefail
umask 077
APP=/opt/tracker
PY="$APP/.venv/bin/python"
fail() { echo "ERROR: $*" >&2; exit 1; }
usage() {
  echo "Usage: sudo bash /opt/tracker/scripts/tracker-targeted-preflight584.sh --base SHA --target SHA --ref release/NAME --browser-module tests/browser/test_csrf_preparations583.py" >&2
  exit 2
}
BASE="" TARGET="" REF="" MODULE=""
while (( $# )); do
  (( $# >= 2 )) || usage
  case "$1" in
    --base) BASE="$2";;
    --target) TARGET="$2";;
    --ref) REF="$2";;
    --browser-module) MODULE="$2";;
    *) usage;;
  esac
  shift 2
done
[[ "$BASE" =~ ^[0-9a-f]{40}$ && "$TARGET" =~ ^[0-9a-f]{40}$ && "$BASE" != "$TARGET" ]] || usage
[[ "$REF" =~ ^release/[a-zA-Z0-9][a-zA-Z0-9._/-]*$ && "$REF" != *..* ]] || usage
[[ "$MODULE" == tests/browser/test_csrf_preparations583.py || "$MODULE" == tests/browser/test_form_overlap586.py || "$MODULE" == tests/browser/test_csrf_bulk587.py ]] || usage
[[ "$(id -u)" == 0 && -x "$PY" && -f /etc/tracker.env ]] || fail "Root on configured Tracker host required"
"$PY" - <<'PY'
import re
from pathlib import Path
labels = []
for line in Path("/etc/tracker.env").read_text().splitlines():
    match = re.match(r'^\s*(?:export\s+)?TRACKER_INSTANCE\s*=(.*)$', line)
    if match:
        labels.append(match.group(1).strip().strip("\"'").upper())
if labels != ["DEV"]:
    raise SystemExit("ERROR: Targeted preflight is DEV-only")
PY
export GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=safe.directory GIT_CONFIG_VALUE_0="$APP"
[[ "$(git -C "$APP" branch --show-current)" == main ]] || fail "Expected installed main checkout"
[[ -z "$(git -C "$APP" status --porcelain)" ]] || fail "Installed checkout must be clean"
[[ "$(git -C "$APP" rev-parse HEAD)" == "$BASE" ]] || fail "Installed revision differs from exact base"
systemctl is-active --quiet tracker || fail "Tracker service is not active"
ROOT="$(mktemp -d /tmp/tracker-preflight-584.XXXXXXXX)"
chmod 700 "$ROOT"
WORK="$ROOT/source"
LOG="$ROOT/preflight.log"
touch "$LOG"
chmod 600 "$LOG"
WORKTREE_ADDED=0
cleanup() {
  local code=$?
  trap - EXIT
  if (( WORKTREE_ADDED )); then
    git -C "$APP" worktree remove --force "$WORK" >/dev/null 2>&1 || true
  fi
  echo "TARGETED_PREFLIGHT_LOG=$LOG"
  echo "TARGETED_PREFLIGHT_EXIT=$code"
  exit "$code"
}
trap cleanup EXIT
exec > >(tee -a "$LOG") 2>&1
echo "TARGETED_PREFLIGHT=START"
echo "TARGETED_BASE=$BASE"
echo "TARGETED_COMMIT=$TARGET"
echo "TARGETED_BROWSER_MODULE=$MODULE"
git -C "$APP" fetch origin main "refs/heads/$REF:refs/remotes/origin/$REF"
[[ "$(git -C "$APP" rev-parse "refs/remotes/origin/$REF")" == "$TARGET" ]] ||
  fail "Release branch does not match exact target"
git -C "$APP" merge-base --is-ancestor "$BASE" "$TARGET" ||
  fail "Candidate is not descended from installed base"
if git -C "$APP" diff --name-only "$BASE" "$TARGET" |
  grep -Eq '^(deploy/|requirements[^/]*|alembic/|alembic.ini|app/(db|models|migrations).py)'; then
  fail "Dependency/schema/system changes require separate review"
fi
git -C "$APP" worktree add --detach "$WORK" "$TARGET"
WORKTREE_ADDED=1
cd "$WORK"
git diff --check "$BASE" "$TARGET"
bash -n scripts/tracker-browser-qualify.sh
bash -n scripts/tracker-targeted-preflight584.sh
"$PY" -m compileall -q app scripts tests
echo "TARGETED_SOURCE_VALIDATION=PASSED"
mapfile -t CHANGED_TESTS < <(
  git diff --name-only --diff-filter=ACMR "$BASE" "$TARGET" -- tests |
  grep -E '^tests/test_[A-Za-z0-9_]+\.py$' || true
)
declare -A TEST_SET=()
TEST_SET[tests/test_browser_qualification511.py]=1
TEST_SET[tests/test_release583_csrf_evidence.py]=1
TEST_SET[tests/test_release583_preparation_fk.py]=1
for test in "${CHANGED_TESTS[@]}"; do TEST_SET["$test"]=1; done
mapfile -t BACKEND_TESTS < <(printf '%s\n' "${!TEST_SET[@]}" | sort)
for test in "${BACKEND_TESTS[@]}"; do [[ -f "$test" ]] || fail "Missing targeted test: $test"; done
BACKEND_DATA="$ROOT/backend-data"
mkdir -m 700 "$BACKEND_DATA"
echo "TARGETED_BACKEND_TESTS=${#BACKEND_TESTS[@]}"
printf 'TARGETED_TEST_FILE=%s\n' "${BACKEND_TESTS[@]}"
env -i HOME=/root PATH=/usr/local/bin:/usr/bin:/bin \
  PYTHONPATH="$WORK" TRACKER_DATA_DIR="$BACKEND_DATA" \
  PYTHONDONTWRITEBYTECODE=1 \
  timeout 180 "$PY" -m pytest -q -n 2 --dist=loadfile \
  --tb=short --maxfail=1 "${BACKEND_TESTS[@]}"
echo "TARGETED_BACKEND=PASSED"
echo "=== TARGETED ISOLATED STRICT-CSRF CHROMIUM ==="
timeout 240 bash "$WORK/scripts/tracker-browser-qualify.sh" \
  "$WORK" "$PY" --targeted-strict "$MODULE"
echo "TARGETED_BROWSER=PASSED"
echo "TARGETED_PREFLIGHT=PASSED"
echo "TARGETED_SCOPE=SOURCE_AND_RELEASE_583_ONLY_NOT_FULL_QUALIFICATION"
