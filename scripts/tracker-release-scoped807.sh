#!/usr/bin/env bash
set -Eeuo pipefail
umask 077
PY="${1:?Python required}"
cd "$(dirname "$0")/.."
export PYTHONPATH="$PWD" PYTHONDONTWRITEBYTECODE=1
[[ "${TRACKER_DATA_DIR:-}" == /tmp/* ]] || { echo "RELEASE_807_BLOCKED=Disposable data required"; exit 1; }
"$PY" -B -m pytest -q --tb=short --disable-warnings \
 tests/test_release807_wellness.py tests/browser/test_anatomy807.py \
 tests/test_release762_progress.py tests/browser/test_progress762.py \
 tests/test_progress_optimization806.py tests/test_health_insights_v23.py \
 tests/test_release635_regimen.py tests/test_release769_google_tasks.py \
 tests/test_release711_blend_dose_corrections.py tests/test_release710_unified_blend_dose.py \
 tests/test_release710_unified_source.py tests/test_blends.py tests/test_release611_blend_calendar.py \
 tests/test_dose_audit_v23.py tests/test_dose_correction_net_inventory.py \
 tests/test_dose_correction_page.py tests/test_dose_disposable_review.py \
 tests/test_dose_transaction_cleanup.py tests/test_dose_unit_aware_supply_inputs.py \
 tests/test_stage17_dose_blend_integrity.py tests/test_health_timeline_filters.py \
 tests/test_shared_optimization806.py tests/test_section_navigation805.py \
 tests/test_visual_mobile_personalization804.py
echo "RELEASE_807_SCOPED=PASSED"
