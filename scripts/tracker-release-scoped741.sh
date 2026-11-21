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
"$PY" -m py_compile app/routers/supplies.py || exit 21
echo "RELEASE_741_COMPILE_SUPPLIES=PASSED"
"$PY" -m py_compile app/routers/pages.py || exit 22
echo "RELEASE_741_COMPILE_PAGES=PASSED"
"$PY" -m py_compile app/routers/calendar.py || exit 23
echo "RELEASE_741_COMPILE_CALENDAR=PASSED"
"$PY" -m py_compile tests/test_release741_integrated_macd_mobile.py || exit 24
echo "RELEASE_741_COMPILE_TESTS=PASSED"
echo "RELEASE_741_COMPILE=PASSED"
"$PY" -c 'from pathlib import Path; from jinja2 import Environment; e=Environment(); [e.parse(Path(p).read_text(encoding="utf-8")) for p in ("app/templates/supplies.html","app/templates/coas.html","app/templates/coa_edit.html","app/templates/vials.html","app/templates/vial_detail.html","app/templates/blend_detail.html","app/templates/labs.html","app/templates/lab_report.html","app/templates/protocols.html","app/templates/calendar.html","app/templates/pages.html","app/templates/page_view.html")]' || exit 31
echo "RELEASE_741_JINJA=PASSED"
# Read-only exception classifier for the disposable initial Supplies GET.
# No raw traceback, user data or private server diagnostics leave the QA worker.
"$PY" - <<'PY'
from pathlib import Path
from tempfile import TemporaryDirectory
import os, runpy, sys
from jinja2 import TemplateError
from sqlalchemy.exc import SQLAlchemyError
from starlette.routing import NoMatchFound
from fastapi import HTTPException
data = runpy.run_path("tests/test_release741_integrated_macd_mobile.py")
with TemporaryDirectory(dir=os.environ["TRACKER_DATA_DIR"]) as tmp:
    g = data["env"].__wrapped__(Path(tmp))
    try:
        client, Session = next(g)
    except TemplateError:
        sys.exit(61)
    except SQLAlchemyError:
        sys.exit(62)
    except NoMatchFound:
        sys.exit(63)
    except HTTPException:
        sys.exit(64)
    except AssertionError:
        sys.exit(65)
    except TypeError:
        sys.exit(66)
    except RuntimeError:
        sys.exit(67)
    except Exception:
        sys.exit(68)
    else:
        g.close()
PY
echo "RELEASE_741_DISPOSABLE_SUPPLIES_GET=PASSED"

# Locate exact first failing operation using immutable nonrepeated stage codes.
"$PY" -m pytest -q --tb=short --maxfail=1 \
  tests/test_release741_integrated_macd_mobile.py::test_741_diag_fixture_supply_list || exit 51
"$PY" -m pytest -q --tb=short --maxfail=1 \
  tests/test_release741_integrated_macd_mobile.py::test_741_diag_seed_and_render || exit 52
"$PY" -m pytest -q --tb=short --maxfail=1 \
  tests/test_release741_integrated_macd_mobile.py::test_741_diag_version_form || exit 53
"$PY" -m pytest -q --tb=short --maxfail=1 \
  tests/test_release741_integrated_macd_mobile.py::test_741_diag_edit_post_response || exit 54
"$PY" -m pytest -q --tb=short --maxfail=1 \
  tests/test_release741_integrated_macd_mobile.py::test_741_diag_edit_persisted_audit || exit 55
echo "RELEASE_741_FIRST_DB_DIAGNOSTICS=PASSED"
# Isolate the first database/API fixture test to produce a distinct stage exit.
"$PY" -m pytest -q --tb=short --maxfail=1 \
  tests/test_release741_integrated_macd_mobile.py::test_741_supply_edit_preserves_ledger_and_records_private_audit || exit 41
echo "RELEASE_741_FIRST_DB_TEST=PASSED"
"$PY" -m pytest -q --tb=short --maxfail=1 tests/test_release741_integrated_macd_mobile.py || exit 42
echo "RELEASE_741_NEW_TESTS=PASSED"
"$PY" -m pytest -q --tb=short --maxfail=1 \
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
  tests/test_record_explorer_template_regression.py || exit 43
echo "RELEASE_741_INTEGRATED_MACD_MOBILE_TESTS=PASSED"
echo "RELEASE_741_SCOPED_QUALIFICATION=PASSED_NOT_FULL_SUITE"
