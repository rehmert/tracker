#!/usr/bin/env bash
set -Eeuo pipefail
umask 077
PY="${1:?Python required}"
cd "$(dirname "$0")/.."
export PYTHONPATH="$PWD" PYTHONDONTWRITEBYTECODE=1
"$PY" -B -m pytest -q -s --tb=no --disable-warnings tests/test_section_navigation805.py tests/test_long_page_navigation.py tests/test_section_deep_links.py tests/test_visual_mobile_personalization804.py
echo "RELEASE_805_SCOPED=PASSED"
