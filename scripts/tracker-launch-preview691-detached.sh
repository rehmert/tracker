#!/usr/bin/env bash
# Ops 691: SHA-pinned detached isolated COA identifier preview, no install.
set -Eeuo pipefail
umask 077
APP=/opt/tracker
OPS=ops/691-detached-preview
REF=release/691-coa-document-identifiers
BASE=6a8cd357e7e8925228d1a37c50572f93c4ec0943
EARLIER_DEV=ae8c75ef39ed26fa505be17e0d8b6152542cbf36
TARGET=8b35c13a68beed4397af7fcbbb14d1b463db5e5c
WORKER_SHA=3edfe4145b445c08cbde77d6d7059e6b52cd19b7
WORKER_PATH=scripts/tracker-preview691-detached-worker.sh
fail(){ echo "RELEASE_691_LAUNCH_ERROR=$*" >&2; exit 1; }
[[ "$(id -u)" -eq 0 && "$(hostname -s)" == tracker-dev ]] ||
  fail "Run as root on tracker-dev"
cd "$APP"
export GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=safe.directory GIT_CONFIG_VALUE_0="$APP"
[[ "$(git branch --show-current)" == main && -z "$(git status --porcelain)" ]] ||
  fail "Require clean DEV main checkout"
DEV_HEAD="$(git rev-parse HEAD)"
[[ "$DEV_HEAD" == "$BASE" || "$DEV_HEAD" == "$EARLIER_DEV" ]] ||
  fail "Isolated preview requires installed DEV 689 or 690"
systemctl is-active --quiet tracker || fail "DEV Tracker service inactive"
git fetch origin "refs/heads/$OPS:refs/remotes/origin/$OPS" "refs/heads/$REF:refs/remotes/origin/$REF"
git merge-base --is-ancestor "$WORKER_SHA" "refs/remotes/origin/$OPS" ||
  fail "Pinned worker missing in operations ref"
[[ "$(git rev-parse "refs/remotes/origin/$REF")" == "$TARGET" ]] ||
  fail "Release ref differs from pinned candidate"
git merge-base --is-ancestor "$BASE" "$TARGET" ||
  fail "Candidate not based on qualified Release 690"
git diff --check "$BASE" "$TARGET"
EXPECTED="$(printf '%s\n' \
  app/migrations.py \
  app/models.py \
  app/routers/coas.py \
  app/static/css/tracker-coa-identifiers691.css \
  app/templates/coa_edit.html \
  scripts/tracker-preview691.sh \
  scripts/tracker-release-scoped691.sh \
  scripts/tracker-release.sh \
  scripts/tracker_schema_review691.py \
  tests/test_coa_document_identifiers691.py | LC_ALL=C sort)"
ACTUAL="$(git diff --name-only "$BASE" "$TARGET" | LC_ALL=C sort)"
[[ "$ACTUAL" == "$EXPECTED" ]] || fail "Unexpected source files"
"$APP/.venv/bin/python" - <<'PY'
import ast, subprocess
target = "8b35c13a68beed4397af7fcbbb14d1b463db5e5c"
for path in (
    "app/models.py", "app/migrations.py", "app/routers/coas.py",
    "scripts/tracker_schema_review691.py", "tests/test_coa_document_identifiers691.py",
):
    ast.parse(
        subprocess.check_output(["git", "show", target + ":" + path], text=True),
        filename=path,
    )
print("RELEASE_691_SYNTAX_PREFLIGHT=PASSED")
PY
for path in scripts/tracker-release.sh scripts/tracker-release-scoped691.sh scripts/tracker-preview691.sh; do
  git show "$TARGET:$path" | bash -n
done
echo "RELEASE_691_SHELL_PREFLIGHT=PASSED"
STAGE="$(mktemp -d /tmp/tracker-691-detached.XXXXXXXX)"
chmod 700 "$STAGE"
WORKER="$STAGE/worker.sh"
git show "$WORKER_SHA:$WORKER_PATH" > "$WORKER"
[[ "$(git hash-object "$WORKER")" == "$(git rev-parse "$WORKER_SHA:$WORKER_PATH")" ]] || {
  rm -rf -- "$STAGE"
  fail "Worker hash mismatch"
}
bash -n "$WORKER"
chmod 700 "$WORKER"
UNIT="tracker-preview691-$(date -u +%Y%m%d%H%M%S)-$$"
echo "RELEASE_691_LAUNCH_UNIT=$UNIT"
if ! systemd-run --no-block --unit="$UNIT" \
  --property=MemoryAccounting=yes \
  --property=MemoryMax=2G \
  --property=TasksMax=96 \
  --property=CPUQuota=200% \
  --property=RuntimeMaxSec=1200 \
  --property=TimeoutStopSec=15 \
  -- /usr/bin/bash "$WORKER"; then
  rm -rf -- "$STAGE"
  fail "Detached preview launch failed"
fi
echo "RELEASE_691_LAUNCH=DETACHED"
echo "RELEASE_691_PREVIEW=STARTED_NOT_YET_QUALIFIED"
echo "RELEASE_691_JOURNAL=journalctl --no-pager -u $UNIT -o cat"
echo "RELEASE_691_STATE=systemctl show $UNIT -p ActiveState -p SubState -p Result -p ExecMainStatus"
echo "RELEASE_691_DATABASES=UNMODIFIED_ISOLATED_PREVIEW"
echo "RELEASE_691_INSTALLATION=NOT_REQUESTED"
