#!/usr/bin/env bash
# Release 706: scoped QA for issue 9 route diagnostics and issue 10 replay.
# Does not install packages, launch browsers, or alter live DEV/PROD.
set -Eeuo pipefail

[[ "$#" == 1 && -x "$1" ]] || {
  echo "Usage: tracker-release-scoped706.sh CONFIGURED_PYTHON" >&2
  exit 2
}
PY="$1"
ROOT="$(cd -- "$(dirname -- "$0")/.." && pwd -P)"
[[ "$PWD" == "$ROOT" && "$ROOT" != /opt/tracker ]] || {
  echo "Release 706 must run inside detached source worktree" >&2
  exit 2
}
bash -n scripts/tracker-issue-review706.sh
bash -n scripts/tracker-release-scoped706.sh
"$PY" -m py_compile \
  scripts/tracker_browser_os_replay706.py \
  scripts/tracker_csrf_survey706.py \
  tests/test_release706_gates.py

"$PY" -m pytest -q --tb=short --maxfail=1 \
  tests/test_release706_gates.py
echo 'RELEASE_706_NEW_SOURCE_CONTRACT=PASSED'

# The six existing session/account routes use their own independent signed
# CSRF scheme. Exercise their positive/forged handlers with strict GLOBAL
# mode enabled on synthetic HTTPS TestClient data, never installed accounts.
TRACKER_CSRF_ENFORCE=1 "$PY" -m pytest -q --tb=short --maxfail=1 \
  tests/test_session_csrf3853.py \
  tests/test_account_security386.py \
  tests/test_user_management479.py \
  tests/test_release589_secondary_strict_csrf.py
echo 'CSRF_706_SESSION_ACCOUNT_STRICT_HTTPS_TESTCLIENT=PASSED_NOT_BROWSER'

# Keep all prior source safety and FastAPI CSRF/negative route qualification,
# including pinned 705 exact source and dependency evidence, without
# repeating the full 16-worker browser suite or downloading any packages.
bash scripts/tracker-release-scoped705.sh "$PY"
echo 'RELEASE_706_PREVIOUS_705_SOURCE=REQUALIFIED'

echo 'RELEASE_706_SOURCE_SCOPED=PASSED'
echo 'RELEASE_706_ISSUES=OPEN_UNTIL_RUNTIME_AND_MANUAL_PROOF'
