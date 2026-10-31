#!/usr/bin/env bash

set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

PYTHON=".venv/bin/python"
REPORT="/tmp/tracker-verification-plus.json"

echo "=============================================="
echo " Tracker Extended Verification"
echo "=============================================="

[[ -x "$PYTHON" ]] || {
    echo "ERROR: Python environment missing"
    exit 1
}

# Preflight is read-only unless --snapshot is supplied.

"$PYTHON" scripts/tracker-preflight.py \
    --json /tmp/tracker-preflight.json

echo
echo "=== Python syntax ==="

"$PYTHON" - <<'PY'
from pathlib import Path
import ast
import sys

root = Path(".")
failures = []

files = sorted(
    list(Path("app").rglob("*.py"))
    + list(Path("scripts").rglob("*.py"))
)

files = [
    path for path in files
    if ".venv" not in path.parts
    and "__pycache__" not in path.parts
]

for path in files:
    try:
        ast.parse(
            path.read_text(encoding="utf-8"),
            filename=str(path),
        )
    except Exception as exc:
        failures.append((str(path), str(exc)))

for path, error in failures:
    print("FAIL:", path, error)

print(
    f"Python: {len(files)} files, "
    f"{len(failures)} failures"
)

if failures:
    sys.exit(1)
PY

echo
echo "=== Bash syntax ==="

bash_count=0

while IFS= read -r -d '' file; do
    bash -n "$file"
    bash_count=$((bash_count + 1))
done < <(
    find scripts \
        -type f \
        -name '*.sh' \
        -print0
)

echo "Bash: $bash_count files checked"

echo
echo "=== Existing quality gate ==="

if [[ -f scripts/tracker-quality-gate.py ]]; then
    "$PYTHON" scripts/tracker-quality-gate.py \
        --json /tmp/tracker-quality-report.json
else
    echo "SKIP: Quality gate not installed"
fi

echo
echo "=== Existing release audit ==="

if [[ -f scripts/tracker-release-audit.py ]]; then
    "$PYTHON" scripts/tracker-release-audit.py \
        --json /tmp/tracker-release-audit.json
else
    echo "SKIP: Release audit not installed"
fi

echo
echo "=== Git whitespace ==="

git diff --check

echo
echo "=== Verification report ==="

"$PYTHON" - <<'PY'
import datetime
import json
from pathlib import Path

reports = {
    "preflight": "/tmp/tracker-preflight.json",
    "quality_gate": "/tmp/tracker-quality-report.json",
    "release_audit": "/tmp/tracker-release-audit.json",
}

result = {
    "timestamp": datetime.datetime.now(
        datetime.timezone.utc
    ).isoformat(),
    "verification": "passed",
    "checks": {},
}

for name, filename in reports.items():
    path = Path(filename)

    if path.exists():
        try:
            data = json.loads(
                path.read_text(encoding="utf-8")
            )

            result["checks"][name] = {
                "available": True,
                "stats": data.get("stats", {}),
                "warnings": len(
                    data.get("warnings", [])
                ),
                "failures": len(
                    data.get(
                        "failures",
                        data.get("errors", []),
                    )
                ),
            }

        except Exception as exc:
            result["checks"][name] = {
                "available": False,
                "error": str(exc),
            }

    else:
        result["checks"][name] = {
            "available": False
        }

Path("/tmp/tracker-verification-plus.json").write_text(
    json.dumps(result, indent=2) + "\n",
    encoding="utf-8",
)

print(
    json.dumps(
        result,
        indent=2,
    )
)
PY

echo
echo "=============================================="
echo " Extended Verification Passed"
echo "=============================================="

echo
echo "Report: $REPORT"
