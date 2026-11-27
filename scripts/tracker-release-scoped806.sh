#!/usr/bin/env bash
set -Eeuo pipefail
umask 077
PY="${1:?Python required}"
cd "$(dirname "$0")/.."
export PYTHONPATH="$PWD" PYTHONDONTWRITEBYTECODE=1
"$PY" -B -m pytest -q -s --tb=short --disable-warnings tests/test_shared_optimization806.py tests/test_release36_40_ui.py tests/test_release769_google_tasks.py tests/test_release635_regimen.py tests/test_health_timeline_filters.py tests/test_visual_mobile_personalization804.py tests/test_progress_optimization806.py tests/test_release762_progress.py tests/test_section_navigation805.py tests/test_long_page_navigation.py tests/test_section_deep_links.py
echo "RELEASE_806_SCOPED=PASSED"
