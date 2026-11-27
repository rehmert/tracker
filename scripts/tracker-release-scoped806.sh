#!/usr/bin/env bash
set -Eeuo pipefail
umask 077
PY="${1:?Python required}"
cd "$(dirname "$0")/.."
export PYTHONPATH="$PWD" PYTHONDONTWRITEBYTECODE=1
"$PY" -B -m pytest -q -s --tb=short --disable-warnings tests/test_progress_optimization806.py tests/test_release762_progress.py tests/test_section_navigation805.py tests/test_long_page_navigation.py tests/test_section_deep_links.py
echo "RELEASE_806_SCOPED=PASSED"
