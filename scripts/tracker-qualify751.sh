#!/usr/bin/env bash
# Release 751: immutable exact-SHA isolated HTTP/HTTPS security qualification.
set -Eeuo pipefail
umask 077
APP=/opt/tracker
PY="$APP/.venv/bin/python"
BASE=2ff72f49449306ea5b11dc9c861d0cac5973131e
REF=release/751-strict-csrf-dev-rollout
die(){ echo "RELEASE_751_BLOCKED=$*" >&2; exit 1; }
[[ $# == 1 && "$1" =~ ^[0-9a-f]{40}$ ]] || die "Exact candidate SHA required"
TARGET="$1"
[[ "$(id -u)" == 0 && "$(hostname -s)" == tracker-dev &&
 -n "$(printenv INVOCATION_ID || true)" ]] || die "Root DEV systemd worker required"
[[ "$(readlink /proc/self/ns/net)" != "$(readlink /proc/1/ns/net)" ]] ||
 die "PrivateNetwork=yes required"
[[ -x "$PY" && -d "$APP/.git" ]] || die "Installed DEV missing"
cd "$APP"
export GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=safe.directory
export GIT_CONFIG_VALUE_0="$APP"
[[ "$(git branch --show-current)" == main &&
 "$(git rev-parse HEAD)" == "$BASE" && -z "$(git status --porcelain)" ]] ||
 die "Clean Release 750 DEV base required"
systemctl is-active --quiet tracker.service || die "DEV service inactive"
exec 9>/run/lock/tracker751-strict-qa.lock
flock -n 9 || die "Concurrent Release 751 QA"
[[ "$(git rev-parse "refs/remotes/origin/$REF")" == "$TARGET" ]] ||
 die "Fetched branch moved"
git merge-base --is-ancestor "$BASE" "$TARGET" || die "Not fast forward"
git diff --check "$BASE" "$TARGET"
while IFS= read -r path; do
 case "$path" in
 scripts/tracker-qualify751.sh|scripts/tracker-install751.sh|\
 scripts/tracker-release-scoped751.sh|scripts/tracker-csrf-dev751.sh|\
 tests/test_release751_csrf_activation.py|\
 tests/browser/test_release727_labs_cards.py|\
 tests/test_release627_csrf_remaining_negative_matrix.py|docs/release-751-csrf-dev.md) ;;
 *) die "Unreviewed path: $path" ;;
 esac
done < <(git diff --name-only "$BASE" "$TARGET")
RUN="$(mktemp -d /tmp/tracker751-strict-qa.XXXXXXXX)"
QA="$RUN/source"
cleanup(){
 local rc=$?
 trap - EXIT
 if [[ -d "$QA" ]] &&
  ! git -C "$APP" worktree remove --force "$QA"; then rc=1; fi
 rm -rf -- "$RUN"
 if [[ "$(git -C "$APP" rev-parse HEAD)" != "$BASE" ||
       "$(git -C "$APP" branch --show-current)" != main ||
       -n "$(git -C "$APP" status --porcelain)" ]]; then rc=1; fi
 echo "RELEASE_751_INSTALLED_DEV=UNMODIFIED"
 echo "RELEASE_751_EXIT_STATUS=$rc"
 exit "$rc"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
git worktree add --detach "$QA" "$TARGET"
[[ "$(git -C "$QA" rev-parse HEAD)" == "$TARGET" ]] || die "Worktree SHA mismatch"
export GIT_CONFIG_COUNT=2
export GIT_CONFIG_KEY_0=safe.directory GIT_CONFIG_VALUE_0="$APP"
export GIT_CONFIG_KEY_1=safe.directory GIT_CONFIG_VALUE_1="$QA"
mkdir -m 700 "$RUN/data"
cd "$QA"
export TRACKER_DATA_DIR="$RUN/data" PYTHONPATH="$QA" PYTHONDONTWRITEBYTECODE=1
"$PY" -B scripts/tracker-impact-preflight604.py --base "$BASE" --target "$TARGET" --root "$QA"
echo "RELEASE_751_IMPACT_PREFLIGHT=PASSED"
bash scripts/tracker-release-scoped751.sh "$PY"
echo "RELEASE_751_ISOLATED_STRICT_BROWSER=STARTED"
# Full output stays inside the private QA worker. Surface only a bounded
# list of synthetic failing test identifiers in GitHub stage receipts.
set +e
timeout 900 bash scripts/tracker-browser-qualify.sh "$QA" "$PY" 2>&1 \
  | tee "$RUN/browser751-private.log"
result=("${PIPESTATUS[@]}")
set -e
if (( result[0] != 0 || result[1] != 0 )); then
  "$PY" - "$RUN/browser751-private.log" <<'PY'
from pathlib import Path
import re, sys
text = Path(sys.argv[1]).read_text(encoding="utf-8", errors="replace")
seen = set()
for line in text.splitlines():
    match = re.match(
        r"^(?:FAILED|ERROR) tests/browser/test_strict_csrf521[.]py::(test_[A-Za-z0-9_]+)",
        line.strip(),
    )
    if match and match.group(1) not in seen:
        seen.add(match.group(1))
        print("FAILED tests/strict751_" + match.group(1) + ".py")
    if len(seen) >= 8:
        break
print("RELEASE_751_BROWSER_DIAGNOSTICS=SANITIZED")
PY
  exit 1
fi
echo "RELEASE_751_DISPOSABLE_HTTP_HTTPS_STRICT_BROWSER=PASSED"
echo "RELEASE_751_QUALIFICATION=PASSED_SCOPED_NO_DEPLOY"
