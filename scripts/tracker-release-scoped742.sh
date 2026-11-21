#!/usr/bin/env bash
# Release 742: bundled CSS, Supplies/Notes bounded reads and mobile shortcuts.
set -Eeuo pipefail
[[ $# == 1 && -x "$1" ]] || { echo "Configured Python required" >&2; exit 2; }
PY="$1"
ROOT="$(cd -- "$(dirname -- "$0")/.." && pwd -P)"
[[ "$PWD" == "$ROOT" && "${TRACKER_DATA_DIR:-}" == /tmp/* ]] ||
  { echo "Release 742 requires isolated source/data" >&2; exit 2; }
for script in scripts/tracker-qualify742.sh scripts/tracker-install742.sh \
  scripts/tracker-release-scoped742.sh scripts/tracker-release.sh; do
  bash -n "$script"
done
"$PY" -m py_compile app/routers/pages.py app/routers/supplies.py \
  tests/test_release742_consolidated_ux_performance.py
"$PY" -c 'from pathlib import Path; from jinja2 import Environment; e=Environment(); [e.parse(Path(p).read_text(encoding="utf-8")) for p in ("app/templates/supplies.html","app/templates/calendar.html")]'
echo "RELEASE_742_SYNTAX_JINJA=PASSED"
"$PY" -m pytest -q --tb=short --maxfail=1 \
  tests/test_release742_consolidated_ux_performance.py || exit 42
echo "RELEASE_742_BUNDLE_READ_BROWSER=PASSED"
"$PY" -m pytest -q --tb=short --maxfail=1 \
  tests/test_release741_integrated_macd_mobile.py \
  tests/test_supply_stock_filters.py \
  tests/test_supply_stock_health.py \
  tests/test_supply_use_preview.py \
  tests/test_calendar_workbench.py \
  tests/test_calendar_review_agenda.py \
  tests/test_record_explorer_template_regression.py || exit 43
echo "RELEASE_742_SCOPED_REGRESSIONS=PASSED"
echo "RELEASE_742_SCOPED_QUALIFICATION=PASSED_NOT_FULL_SUITE"
