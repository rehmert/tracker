#!/usr/bin/env bash
# Guarded DEV Release 645 launcher, pinned to exact candidate Git object.
set -Eeuo pipefail
umask 077
APP=/opt/tracker
REF=release/645-coa-default-document
BASE=5bc0894c2c2865856856298083ca21bc62d00069
fail() { echo "COA_645_DEPLOY=FAILED: $*" >&2; exit 1; }
[[ "$#" == 1 && "$1" =~ ^[0-9a-f]{40}$ ]] || fail "Pass exact expected candidate SHA as first argument"
EXPECTED_TARGET="$1"
[[ "$(id -u)" == 0 && -x "$APP/.venv/bin/python" && -f /etc/tracker.env ]] || fail "Requires configured Tracker and root"
"$APP/.venv/bin/python" - <<'PY'
from pathlib import Path
import re
values=[]
for line in Path("/etc/tracker.env").read_text().splitlines():
 m=re.match(r'^\s*(?:export\s+)?TRACKER_INSTANCE\s*=(.*)$',line)
 if m: values.append(m.group(1).strip().strip(chr(34)).strip(chr(39)).upper())
assert values == ["DEV"], "DEV only"
PY
g() { git -c safe.directory="$APP" -C "$APP" "$@"; }
[[ "$(g branch --show-current)" == main && -z "$(g status --porcelain)" ]] || fail "Expected clean installed main"
[[ "$(g rev-parse HEAD)" == "$BASE" ]] || fail "Expected installed Release 644"
systemctl is-active --quiet tracker || fail "Tracker service inactive"
g fetch origin main "refs/heads/$REF:refs/remotes/origin/$REF"
TARGET="$(g rev-parse "refs/remotes/origin/$REF")"
g merge-base --is-ancestor "$BASE" "$TARGET" || fail "Target not descended from installed base"
[[ "$TARGET" == "$EXPECTED_TARGET" ]] || fail "Branch moved beyond pinned candidate"
DIR="$(mktemp -d /tmp/tracker-coa645-runner.XXXXXXXX)"
cleanup() {
 if [[ -d "$DIR/candidate" ]]; then g worktree remove --force "$DIR/candidate" >/dev/null 2>&1 || true; fi
 rm -f "$DIR/runner.sh"
 rmdir "$DIR" || true
}
trap cleanup EXIT
EXPECTED="$(g rev-parse "$TARGET:scripts/tracker-release.sh")"
g show "$TARGET:scripts/tracker-release.sh" > "$DIR/runner.sh"
[[ "$(g hash-object "$DIR/runner.sh")" == "$EXPECTED" ]] || fail "Runner blob differs from pinned candidate"
bash -n "$DIR/runner.sh"
# Fail before the expensive qualification worker if previous evidence
# cannot be reused, without modifying the installed DEV environment.
g worktree add --detach "$DIR/candidate" "$TARGET"
# Preflight the independent receipt validator against the exact resume-mode
# marker contract before entering a deployment that might otherwise roll back.
"$APP/.venv/bin/python" - "$DIR/candidate" "$DIR/runner.sh" <<'PY'
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import sys

qa, runner = Path(sys.argv[1]), Path(sys.argv[2])
source = runner.read_text()
resume = source.split('if [[ "$RESUME_645_VERIFIED" == 1 ]]; then', 1)[-1]
resume = resume.split('\n  else', 1)[0]
if 'echo "FOCUSED_RELEASE_GATE=PASSED"' not in resume:
    raise SystemExit("COA_645_RESUME_DENIED=focused receipt marker absent from resume branch")
spec = spec_from_file_location("receipt577", qa / "scripts/tracker_dev_log577.py")
validator = module_from_spec(spec)
spec.loader.exec_module(validator)
target = "a" * 40
markers = [
    "Started: 2026-11-16T04:00:00+00:00; instance: DEV",
    f"CANDIDATE_COMMIT={target}",
    "RELEASE_604_FOCUSED_PREFLIGHT=PASSED",
    "COA_645_RESUME_FULL_TEST_REUSE=VERIFIED",
    "QA_FULL_REQUIRED=0",
    "COA_645_FULL_QUALIFICATION_REUSE=PASSED",
    "FOCUSED_RELEASE_GATE=PASSED",
    "=== ISOLATED RESTORE VERIFICATION PASSED ===",
    " TRACKER RELEASE DEPLOYMENT SUCCESS",
    "EXIT_STATUS=0",
    "Finished: 2026-11-16T04:01:00+00:00",
]
result = validator.validated_evidence("\n".join(markers) + "\n", target)
if f"DEV_QUALIFIED_COMMIT={target}" not in result:
    raise SystemExit("COA_645_RESUME_DENIED=receipt validator returned no exact-commit receipt")
print("COA_645_RESUME_RECEIPT_CONTRACT=PASSED")
PY
"$APP/.venv/bin/python" "$DIR/candidate/scripts/tracker-resume-evidence645.py" \
 --app "$APP" --qa "$DIR/candidate" --base "$BASE" --target "$TARGET" ||
 fail "Prior full qualification evidence could not be verified"
g worktree remove --force "$DIR/candidate"
echo "COA_645_BASE=$BASE"
echo "COA_645_TARGET=$TARGET"
echo "COA_645_EXPECTED_SCOPE=DEV_ONLY"
bash "$DIR/runner.sh" \
 --instance DEV --base "$BASE" --target "$TARGET" \
 --ref "$REF" --db-migration --reviewed-coa-645 --resume-verified-645
