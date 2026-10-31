#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

echo "===================================="
echo " Tracker Verification"
echo "===================================="

if [[ ! -x .venv/bin/python ]]; then
    echo "ERROR: Missing Python environment"
    exit 1
fi

echo
echo "=== Existing UI regression tests ==="

if [[ -f scripts/tracker-ui-regression.py ]]; then
    .venv/bin/python \
        scripts/tracker-ui-regression.py
else
    echo "SKIP: Original UI regression script absent"
fi

echo
echo "=== Existing quality gate ==="

if [[ -f scripts/tracker-quality-gate.py ]]; then
    .venv/bin/python \
        scripts/tracker-quality-gate.py \
        --json /tmp/tracker-quality-report.json
else
    echo "SKIP: Original quality gate absent"
fi

echo
echo "=== Release audit ==="

.venv/bin/python \
    scripts/tracker-release-audit.py \
    --json /tmp/tracker-release-audit.json

echo
echo "=== Git whitespace validation ==="

git diff --check

echo
echo "===================================="
echo " Tracker Verification Complete"
echo "===================================="

echo
echo "Reports:"
echo "  /tmp/tracker-quality-report.json"
echo "  /tmp/tracker-release-audit.json"
