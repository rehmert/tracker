#!/usr/bin/env bash
set -Eeuo pipefail

cd "$(dirname "$0")/.."

echo "=== Tracker JavaScript Validation ==="
echo "Node.js: $(node --version)"
echo

if [[ ! -d app/static/js ]]; then
    echo "ERROR: app/static/js directory not found."
    exit 1
fi

checked=0
failed=0

while IFS= read -r -d '' file; do
    checked=$((checked + 1))

    if node --check "$file"; then
        printf 'PASS: %s\n' "$file"
    else
        printf 'FAIL: %s\n' "$file"
        failed=$((failed + 1))
    fi
done < <(
    find app/static/js \
        -type f \
        -name '*.js' \
        -print0 |
    sort -z
)

echo
echo "Files checked: $checked"
echo "Failures:      $failed"

if (( checked == 0 )); then
    echo "ERROR: No JavaScript files found."
    exit 1
fi

if (( failed > 0 )); then
    echo "ERROR: JavaScript validation failed."
    exit 1
fi

echo "PASS: All JavaScript files passed syntax validation."
