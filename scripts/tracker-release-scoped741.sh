#!/usr/bin/env bash
# Release 741 combined inventory, certificates, labs, protocols, calendar, Notes and UX tests.
set -Eeuo pipefail
[[ $# == 1 && -x "$1" ]] || { echo "Configured Python required" >&2; exit 2; }
PY="$1"
ROOT="$(cd -- "$(dirname -- "$0")/.." && pwd -P)"
[[ "$PWD" == "$ROOT" && "${TRACKER_DATA_DIR:-}" == /tmp/* ]] ||
  { echo "Release 741 requires isolated source/data" >&2; exit 2; }
for script in scripts/tracker-qualify741.sh scripts/tracker-install741.sh \
  scripts/tracker-release-scoped741.sh scripts/tracker-release.sh; do
  bash -n "$script"
done
"$PY" -m py_compile app/routers/supplies.py app/routers/pages.py \
  app/routers/calendar.py tests/test_release741_integrated_macd_mobile.py
"$PY" -c 'from pathlib import Path; from jinja2 import Environment; e=Environment(); [e.parse(Path(p).read_text(encoding="utf-8")) for p in ("app/templates/supplies.html","app/templates/coas.html","app/templates/coa_edit.html","app/templates/vials.html","app/templates/vial_detail.html","app/templates/blend_detail.html","app/templates/labs.html","app/templates/lab_report.html","app/templates/protocols.html","app/templates/calendar.html","app/templates/pages.html","app/templates/page_view.html")]'
"$PY" -m pytest -q --tb=short --maxfail=1 \
  tests/test_release741_integrated_macd_mobile.py \
  tests/test_supply_stock_health.py \
  tests/test_supply_stock_filters.py \
  tests/test_supply_use_preview.py \
  tests/test_coa_manage_actions653.py \
  tests/test_coa_documents_ui649.py \
  tests/test_vial_inventory_reports.py \
  tests/test_lab_entry_review_ux.py \
  tests/test_protocol_dates_save.py \
  tests/test_protocol_schedule_preview.py \
  tests/test_calendar_review_agenda.py \
  tests/test_calendar_workbench.py \
  tests/test_record_explorer_template_regression.py
echo "RELEASE_741_INTEGRATED_MACD_MOBILE_TESTS=PASSED"
echo "RELEASE_741_SCOPED_QUALIFICATION=PASSED_NOT_FULL_SUITE"
