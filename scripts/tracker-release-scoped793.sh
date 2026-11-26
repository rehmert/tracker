#!/usr/bin/env bash
# Release 793: unified visual design and navigation, notes and browser regression only.
set -Eeuo pipefail
umask 077
PY="${1:-}"
[[ -n "$PY" && -x "$PY" ]] || { echo "RELEASE_793_BLOCKED=Python missing" >&2; exit 1; }
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
export PYTHONPATH="$ROOT" PYTHONDONTWRITEBYTECODE=1
"$PY" -B -m pytest -q --tb=short --disable-warnings \
 "tests/test_design_system793.py" \
 "tests/test_navigation_focus.py" \
 "tests/test_nav_titlecase.py" \
 "tests/test_navigation_productivity.py" \
 "tests/test_release775_google_tasks_navigation.py" \
 "tests/test_release776_google_tasks_focus.py" \
 "tests/test_headings531.py" \
 "tests/test_server_theme510.py" \
 "tests/test_template_engine_consistency.py" \
 "tests/test_release749_mobile_drawer.py" \
 "tests/test_compact_daily_actions791.py" \
 "tests/test_consolidated_workspaces792.py" \
 "tests/test_integrated_daily790.py" \
 "tests/test_calendar_action_buttons787.py"
echo "RELEASE_793_SCOPED=PASSED"
