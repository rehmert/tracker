#!/usr/bin/env bash
# Reusable guarded DEV-controlled PROD promotion. Update only on tooling branch.
set -Eeuo pipefail
umask 077

APP=/opt/tracker
PY="$APP/.venv/bin/python"
PROMOTER="$APP/scripts/tracker_promote568.py"
LOG_DIR=/etc/tracker-release/operation-logs

fail() { printf 'BLOCKED: %s\n' "$*" >&2; exit 1; }
g() { git -c safe.directory="$APP" -C "$APP" "$@"; }
sshprod() {
  ssh -n -o BatchMode=yes -o ConnectTimeout=10 \
    -o StrictHostKeyChecking=yes -o ClearAllForwardings=yes \
    -o ServerAliveInterval=30 -o ServerAliveCountMax=6 \
    root@tracker-prod "$@"
}

[[ "$EUID" -eq 0 && "$(hostname -s)" == tracker-dev ]] ||
  fail "Run as root on tracker-dev"
[[ -x "$PY" && -f "$PROMOTER" && -d "$APP/.git" ]] ||
  fail "Trusted DEV release tooling is unavailable"
[[ "$#" -le 1 ]] || fail "Usage: tracker-release-prod.sh [expected-release-number]"
EXPECTED=""
if (( $# == 1 )); then EXPECTED="$1"; fi
[[ -z "$EXPECTED" || "$EXPECTED" =~ ^[1-9][0-9]{0,5}$ ]] ||
  fail "Expected release must be an integer"

exec 9>/run/lock/tracker-release-prod-wrapper.lock
flock -n 9 || fail "Another PROD wrapper is already running"

[[ "$(g branch --show-current)" == main ]] ||
  fail "DEV must be on installed main branch"
[[ -z "$(g status --porcelain)" ]] ||
  fail "DEV checkout contains uncommitted changes"
systemctl is-active --quiet tracker ||
  fail "DEV Tracker service is inactive"

TARGET="$(g rev-parse HEAD)"
[[ "$TARGET" =~ ^[0-9a-f]{40}$ ]] || fail "Invalid DEV commit"
RELEASE="$(g log -1 --format=%s | sed -nE 's/^Release ([1-9][0-9]{0,5}):.*/\1/p')"
[[ -n "$RELEASE" ]] ||
  fail "Cannot determine DEV release from installed commit title"
[[ -z "$EXPECTED" || "$EXPECTED" == "$RELEASE" ]] ||
  fail "Installed DEV release $RELEASE is not requested Release $EXPECTED"

remote_refs="$(g ls-remote --heads origin "refs/heads/release/$RELEASE-*")" ||
  fail "Unable to check release refs on origin"
REF=""
count=0
while read -r sha gitref; do
  if [[ "$sha" == "$TARGET" &&
        "$gitref" =~ ^refs/heads/release/[1-9][0-9]{0,5}-[a-zA-Z0-9._/-]+$ ]]; then
    REF="$(printf '%s\n' "$gitref" | sed 's|^refs/heads/||')"
    (( count += 1 ))
  fi
done <<<"$remote_refs"
(( count == 1 )) ||
  fail "Expected exactly one release branch pointing to installed DEV SHA; found $count"

prod_info="$(sshprod '
  set -eu
  test "$(hostname -s)" = tracker-prod
  test "$(git -c safe.directory=/opt/tracker -C /opt/tracker branch --show-current)" = main
  systemctl is-active --quiet tracker
  git -c safe.directory=/opt/tracker -C /opt/tracker rev-parse HEAD
  git -c safe.directory=/opt/tracker -C /opt/tracker log -1 --format=%s
')" || fail "Cannot securely inspect active tracker-prod"
PROD_BASE="$(printf '%s\n' "$prod_info" | sed -n '1p')"
PROD_TITLE="$(printf '%s\n' "$prod_info" | sed -n '2p')"
[[ "$PROD_BASE" =~ ^[0-9a-f]{40}$ && -n "$PROD_TITLE" ]] ||
  fail "Invalid installed PROD release information"

g cat-file -e "$PROD_BASE^{commit}" ||
  fail "Installed PROD commit is not in the DEV repository"
g merge-base --is-ancestor "$PROD_BASE" "$TARGET" ||
  fail "Installed PROD is not an ancestor of DEV release"

main_info="$(g ls-remote --heads origin refs/heads/main)" ||
  fail "Could not verify current GitHub main"
read -r MAIN_SHA MAIN_REF <<<"$main_info"
[[ "$MAIN_SHA" =~ ^[0-9a-f]{40}$ && "$MAIN_REF" == refs/heads/main ]] ||
  fail "Invalid GitHub main response"
[[ "$MAIN_SHA" == "$PROD_BASE" || "$MAIN_SHA" == "$TARGET" ]] ||
  fail "GitHub main is neither installed PROD nor qualified DEV target"

printf '\n========================================\n'
printf ' TRACKER RELEASE %s - DEV-CONTROLLED PROD\n' "$RELEASE"
printf '========================================\n'
printf 'DEV:  %s (%s)\n' "$TARGET" "$REF"
printf 'PROD: %s (%s)\n' "$PROD_BASE" "$PROD_TITLE"
printf 'MAIN: %s\n\n' "$MAIN_SHA"

if [[ "$PROD_BASE" == "$TARGET" ]]; then
  [[ "$MAIN_SHA" == "$TARGET" ]] ||
    fail "PROD already installed but GitHub main does not match"
  echo "PROD_ALREADY_AT_TARGET=$TARGET"
  echo "PROD_SERVICE=ACTIVE"
  echo "NO_DEPLOYMENT_NEEDED=YES"
  exit 0
fi

[[ ! -L "$LOG_DIR" ]] || fail "Unsafe log directory symlink"
install -d -m 700 -- "$LOG_DIR"
[[ ! -L "$LOG_DIR" && "$(stat -c '%u:%a' "$LOG_DIR")" == "0:700" ]] ||
  fail "Log directory must be root-owned, mode 0700"
LOG="$(mktemp "$LOG_DIR/release-$RELEASE-prod.XXXXXXXX.log")"
chmod 600 "$LOG"
printf 'Live deployment log (root-only): %s\n' "$LOG"

(
  printf '=== PREFLIGHT (NO PROD MUTATION) ===\n'
  "$PY" -u "$PROMOTER" \
    --release "$RELEASE" --target "$TARGET" \
    --prod-base "$PROD_BASE" --ref "$REF"

  printf '\n=== SIGNED APPROVAL AND GUARDED PROD DEPLOY ===\n'
  "$PY" -u "$PROMOTER" \
    --release "$RELEASE" --target "$TARGET" \
    --prod-base "$PROD_BASE" --ref "$REF" --execute
) >>"$LOG" 2>&1 &
JOB=$!

tail -n +1 -F --pid="$JOB" -- "$LOG" || true
RC=0
wait "$JOB" || RC=$?
if (( RC != 0 )); then
  printf '\nDEPLOYMENT_NOT_VERIFIED=YES (exit %s)\nLog: %s\n' "$RC" "$LOG" >&2
  echo "Inspect PROD and main before any retry: promotion may be partial." >&2
  exit "$RC"
fi

grep -Fxq 'DEV_CONTROLLED_RELEASE=SUCCESS' "$LOG" ||
  fail "Signed promotion success evidence missing"
grep -Fxq "PROD_INSTALLED_COMMIT=$TARGET" "$LOG" ||
  fail "Exact PROD installation marker missing"

final_info="$(sshprod '
  set -eu
  git -c safe.directory=/opt/tracker -C /opt/tracker rev-parse HEAD
  systemctl is-active tracker
')" || fail "Post-deploy PROD verification unavailable"
FINAL_PROD="$(printf '%s\n' "$final_info" | sed -n '1p')"
FINAL_SERVICE="$(printf '%s\n' "$final_info" | sed -n '2p')"
main_info="$(g ls-remote --heads origin refs/heads/main)" ||
  fail "Post-deploy GitHub main verification unavailable"
read -r FINAL_MAIN FINAL_REF <<<"$main_info"
[[ "$FINAL_PROD" == "$TARGET" && "$FINAL_SERVICE" == active &&
   "$FINAL_MAIN" == "$TARGET" && "$FINAL_REF" == refs/heads/main ]] ||
  fail "Final PROD commit/service/GitHub main does not match target"

printf '\nPROD_INSTALLED_COMMIT=%s\nGITHUB_MAIN=%s\n' "$FINAL_PROD" "$FINAL_MAIN"
printf 'PROD_SERVICE=ACTIVE\nDEV_CONTROLLED_RELEASE=SUCCESS\n'
printf 'TRACKER_RELEASE_PROD=VERIFIED\n'
printf 'Full live log: %s\n' "$LOG"
