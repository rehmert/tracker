#!/usr/bin/env bash
# Tracker release watcher: GitHub-managed, exact-request, fail-closed DEV progress.
# The immutable GitHub receipt, not systemd exit status, decides success.
set -Eeuo pipefail
umask 077

readonly APP='/opt/tracker'
readonly UNIT='tracker-release-agent.service'
readonly QUEUE_REF='refs/remotes/origin/tracker-release-requests'
readonly RECEIPTS_REF='refs/remotes/origin/tracker-release-receipts'
readonly LOGDIR='/var/log/tracker-release-agent'

fail() { printf 'ERROR: %s\n' "$*" >&2; exit 1; }
[[ $EUID -eq 0 ]] || fail 'Run as root: sudo /root/tracker-release.sh'
[[ "$(hostname -s)" == 'tracker-dev' ]] || fail 'This helper runs only on tracker-dev'
[[ -d "$APP/.git" ]] || fail "Missing installed Tracker checkout: $APP"
for command in git python3 systemctl journalctl tail; do
  command -v "$command" >/dev/null 2>&1 || fail "Missing command: $command"
done
[[ -n "$UNIT" && "$UNIT" == 'tracker-release-agent.service' ]] || fail 'Internal unit configuration is invalid'
[[ -n "$LOGDIR" && "$LOGDIR" == '/var/log/tracker-release-agent' ]] || fail 'Internal log directory is invalid'
[[ -d "$LOGDIR" ]] || fail "Agent log directory missing: $LOGDIR"

GIT=(git -c "safe.directory=$APP" -C "$APP")
fetch_branch() {
  local branch="$1"
  "${GIT[@]}" fetch --quiet --no-tags origin \
    "refs/heads/$branch:refs/remotes/origin/$branch"
}

printf '\n=== Tracker release watcher / Checking GitHub queue ===\n'
fetch_branch tracker-release-requests || fail 'Could not fetch release request branch'
REQUEST_JSON="$("${GIT[@]}" show "$QUEUE_REF:control/current.json")" || fail 'Cannot read current release request'

# Extraction is atomic: invalid JSON, wrong types, blank IDs and unknown
# actions abort BEFORE starting a service or constructing a log path.
META="$(python3 -c '
import json, re, sys
try:
    r = json.load(sys.stdin)
    valid = isinstance(r, dict) and type(r.get("schema")) is int and r.get("schema") == 1
    request_id = r.get("request_id") if valid else None
    action = r.get("action") if valid else None
    release = r.get("release") if valid else None
    target = r.get("target") if valid else None
    base = r.get("base") if valid else None
    ref = r.get("ref") if valid else None
    valid = valid and (
        isinstance(request_id, str) and re.fullmatch(r"r[1-9][0-9]{0,5}-[a-z0-9]{8,20}", request_id)
        and action in {"qualify", "dev_install", "prod_preflight", "prod_deploy"}
        and type(release) is int and 1 <= release <= 999999
        and isinstance(target, str) and re.fullmatch(r"[0-9a-f]{40}", target)
        and isinstance(base, str) and re.fullmatch(r"[0-9a-f]{40}", base)
        and isinstance(ref, str) and re.fullmatch(r"release/[1-9][0-9]{0,5}-[a-z0-9-]+", ref)
        and int(ref.split("/", 1)[1].split("-", 1)[0]) == release
    )
    if not valid:
        raise ValueError("invalid fields")
except (ValueError, TypeError, json.JSONDecodeError, AttributeError):
    print("ERROR: Invalid or incomplete release request JSON; agent NOT started", file=sys.stderr)
    sys.exit(1)
print("\t".join((request_id, action, str(release), target, base, ref)))
' <<< "$REQUEST_JSON")" || fail 'Refusing to trigger an unidentified release'

IFS=$'\t' read -r REQUEST_ID ACTION RELEASE TARGET BASE RELEASE_REF <<< "$META"
[[ -n "$REQUEST_ID" && -n "$ACTION" && -n "$RELEASE" && -n "$TARGET" && -n "$BASE" && -n "$RELEASE_REF" ]] || fail 'Missing parsed release metadata; agent NOT started'
[[ "$REQUEST_ID" =~ ^r[1-9][0-9]{0,5}-[a-z0-9]{8,20}$ ]] || fail 'Malformed request ID'
readonly REQUEST_ID ACTION RELEASE TARGET BASE RELEASE_REF
readonly LOG="$LOGDIR/$REQUEST_ID.log"

# Only observe/trigger DEV stages. PROD requires separate explicit approval
# through the signed DEV-controlled promotion workflow.
if [[ "$ACTION" == 'prod_preflight' || "$ACTION" == 'prod_deploy' ]]; then
  fail 'This watcher does not start PROD stages. Use the authorized PROD promotion workflow.'
fi

printf 'Release: %s\nStage: %s\nRequest: %s\nCommit: %.12s\nLog: %s\n\n' \
  "$RELEASE" "$ACTION" "$REQUEST_ID" "$TARGET" "$LOG"

TAIL_PID=''
cleanup() {
  if [[ -n "$TAIL_PID" ]]; then
    kill "$TAIL_PID" 2>/dev/null || true
    wait "$TAIL_PID" 2>/dev/null || true
    TAIL_PID=''
  fi
}
trap cleanup EXIT
trap 'printf "\nStopped watching; the DEV agent continues independently.\n"; exit 130' INT TERM

# A request may have finished before this script was invoked. Do not start
# the agent needlessly for an immutable, already-published result.
RECEIPT_JSON=''
fetch_receipt() {
  fetch_branch tracker-release-receipts >/dev/null 2>&1 || return 1
  RECEIPT_JSON="$("${GIT[@]}" show "$RECEIPTS_REF:receipts/$REQUEST_ID.json" 2>/dev/null)" || return 1
  [[ -n "$RECEIPT_JSON" ]]
}

print_receipt() {
  printf '\n=== Verified GitHub release receipt ===\n'
  python3 -c '
import json, sys
expected_id, expected_action, expected_release, expected_target, expected_base, expected_ref = sys.argv[1:]
try:
    receipt = json.load(sys.stdin)
    if not isinstance(receipt, dict):
        raise ValueError("not an object")
    for key, expected in (("request_id", expected_id), ("action", expected_action),
                          ("release", int(expected_release)), ("target", expected_target),
                          ("base", expected_base), ("ref", expected_ref)):
        if receipt.get(key) != expected:
            raise ValueError("Receipt mismatch: " + key)
    status = receipt.get("status")
    if status not in {"passed", "failed", "blocked", "unknown"}:
        raise ValueError("Invalid receipt status")
    # A reported pass also needs the authoritative stage success marker.
    if status == "passed":
        markers = receipt.get("markers")
        if not isinstance(markers, list):
            raise ValueError("Missing stage markers")
        if expected_action == "qualify" and (
            "RELEASE_" + expected_release + "_QUALIFICATION=PASSED_SCOPED_NO_DEPLOY"
        ) not in markers:
            raise ValueError("Qualification success marker missing")
        if expected_action == "dev_install" and (
            "RELEASE_" + expected_release + "_DEV_INSTALL=SUCCESS"
        ) not in markers:
            raise ValueError("DEV installation success marker missing")
except (ValueError, TypeError, json.JSONDecodeError) as exc:
    print("ERROR: Could not verify release receipt: " + str(exc), file=sys.stderr)
    sys.exit(1)
print("Request:", expected_id)
print("Release:", expected_release)
print("Stage:", expected_action)
print("Status:", status)
print("Exit code:", receipt.get("exit_code"))
print("Commit:", expected_target)
for item in receipt.get("test_counts", []):
    if isinstance(item, str): print("Tests:", item)
for marker in receipt.get("markers", []):
    if isinstance(marker, str): print("Marker:", marker)
if receipt.get("failure_category"):
    print("Failure category:", receipt["failure_category"])
if receipt.get("failed_tests"):
    print("Failed test files:", ", ".join(str(x) for x in receipt["failed_tests"]))
if status != "passed" or receipt.get("exit_code") != 0:
    sys.exit(2)
' "$REQUEST_ID" "$ACTION" "$RELEASE" "$TARGET" "$BASE" "$RELEASE_REF" <<< "$RECEIPT_JSON"
}

if fetch_receipt; then
  printf 'This request already has a published receipt. No service restart needed.\n'
  if [[ -f "$LOG" ]]; then
    printf '\n=== Last 30 lines of the completed local log ===\n'
    tail -n 30 -- "$LOG"
  fi
  print_receipt
  exit $?
fi

printf 'Triggering queued stage (does not create a new request)...\n'
STARTED="$(date --iso-8601=seconds)"
systemctl start --no-block "$UNIT" || fail "Could not start $UNIT"
printf 'Watching agent journal while waiting for request log...\n'

# Show journal every ~5s until the exact request log exists. Stop early
# when the oneshot service has ended; do not tail a guessed/stale log.
log_found=0
for ((i=0; i<180; i++)); do
  if [[ -f "$LOG" ]]; then log_found=1; break; fi
  STATE="$(systemctl show "$UNIT" --property=ActiveState --value)" || fail 'Cannot query agent state'
  if [[ "$STATE" == inactive || "$STATE" == failed ]]; then
    if (( i >= 4 )); then break; fi
  fi
  if (( i % 10 == 0 )); then
    printf '\n--- Agent journal (state: %s) ---\n' "$STATE"
    journalctl -u "$UNIT" --since "$STARTED" -n 8 --no-pager -o cat || true
  fi
  sleep 0.5
done

if (( log_found )); then
  printf '\n=== Following %s ===\n' "$REQUEST_ID"
  STATE="$(systemctl show "$UNIT" --property=ActiveState --value)" || fail 'Cannot query agent state'
  if [[ "$STATE" == active || "$STATE" == activating || "$STATE" == deactivating ]]; then
    tail -n 25 -F -- "$LOG" &
    TAIL_PID=$!
    for ((i=0; i<3900; i++)); do
      STATE="$(systemctl show "$UNIT" --property=ActiveState --value)" || fail 'Cannot query agent state'
      [[ "$STATE" == active || "$STATE" == activating || "$STATE" == deactivating ]] || break
      sleep 1
    done
    sleep 1
    cleanup
    [[ "$STATE" != active && "$STATE" != activating && "$STATE" != deactivating ]] || fail 'Agent still running after monitor timeout; release outcome unknown'
  else
    tail -n 60 -- "$LOG"
  fi
else
  printf '\nNo execution log found for %s; checking agent journal and receipt.\n' "$REQUEST_ID"
fi

printf '\n=== Agent completion journal ===\n'
journalctl -u "$UNIT" --since "$STARTED" -n 25 --no-pager -o cat || true

# The service can be green while the actual stage failed. Wait for its
# published immutable receipt. Never interpret systemctl status as success.
for ((i=0; i<15; i++)); do
  if fetch_receipt; then
    print_receipt
    exit $?
  fi
  sleep 2
done
fail "No published receipt for $REQUEST_ID. Examine journal above; do not repeat a possibly completed deployment."
