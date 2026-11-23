#!/usr/bin/env bash
set -Eeuo pipefail
umask 077
PY="$1"
[[ -n "$PY" && -x "$PY" ]] || {
  echo 'RELEASE_758_BLOCKED=Python missing' >&2
  exit 1
}
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
export PYTHONPATH="$ROOT" PYTHONDONTWRITEBYTECODE=1
"$PY" -B -m pytest -q --tb=short --disable-warnings \
  tests/test_release758_vial_label_dose.py \
  tests/test_release758_vial_label_fourline.py \
  tests/test_release758_vial_production_date.py \
  tests/test_release758_vial_label_30x15.py \
  tests/test_release758_vial_label_40x20.py \
  tests/test_release758_schema_review.py \
  tests/test_bulk_vial_stage5.py \
  tests/test_bulk_vials.py \
  tests/test_mixed_purchases.py \
  tests/test_release423.py \
  tests/test_vial_label_sheets447.py \
  tests/test_vial_label_rotation431.py \
  tests/test_vial_label_direct450.py \
  tests/test_label_preview_zoom449.py \
  tests/test_release633_pk_label_repro.py \
  tests/test_release605_vendor_label_ux.py
echo 'RELEASE_758_SCOPED=PASSED'
