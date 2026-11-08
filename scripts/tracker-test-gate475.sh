#!/usr/bin/env bash
set -euo pipefail

APP=/opt/tracker
PY="$APP/.venv/bin/python"

[[ -x "$PY" ]] || {
    echo "ERROR: Tracker virtualenv missing"
    exit 1
}

cd "$APP"

MODE="${1:-}"

case "$MODE" in
    non-browser)
        echo "=== COMPLETE NON-BROWSER REGRESSION SUITE ==="
        echo "Browser tests excluded: require live"
        echo "authenticated browser fixture."

        "$PY" -m pytest \
            -q tests \
            --ignore=tests/browser \
            --ignore=tests/test_bulk_vial_browser.py \
            --ignore=tests/test_bulk_vial_guided_browser.py \
            --ignore=tests/test_bulk_delete_browser.py \
            --ignore=tests/test_purchase_vial_browser.py \
            --ignore=tests/test_stage33_browser_sorting.py \
            --ignore=tests/test_health_timeline_dates_browser.py \
            --ignore=tests/test_vitals_csv_browser.py \
            --disable-warnings \
            --tb=short

        echo "=== NON-BROWSER REGRESSION SUCCESS ==="
        ;;

    multiuser)
        echo "=== MULTI-USER SECURITY ACCEPTANCE ==="

        "$PY" -m pytest -q \
            tests/test_multiuser_launch475.py \
            tests/test_multiuser_audit474.py \
            tests/test_unified_login473.py \
            tests/test_secondary_preview430.py \
            tests/test_secondary_files472.py \
            tests/test_secondary_attachments471.py \
            tests/test_secondary_food_inventory_orm470.py \
            tests/test_secondary_recent_orm469.py \
            tests/test_secondary_orm468.py \
            tests/test_secondary_request_db467.py \
            tests/test_secondary_cutover466.py \
            tests/test_secondary_account465.py \
            tests/test_secondary_workspace464.py \
            tests/test_secondary_integration440.py \
            tests/test_secondary_private_workflow440.py \
            tests/test_secondary_sessions441.py \
            tests/test_secondary_password451.py \
            tests/test_request_scope393.py \
            tests/test_scoped_db390.py \
            --disable-warnings \
            --tb=short

        echo "=== MULTI-USER SECURITY SUCCESS ==="
        ;;

    browser)
        echo "=== DISPOSABLE BROWSER ACCEPTANCE ==="
        # Never run browser mutations against an installed Tracker service.
        # The candidate runner starts its own loopback HTTP/HTTPS servers and
        # uses an independent temporary SQLite directory.
        CANDIDATE="${TRACKER_BROWSER_CANDIDATE:-}"
        [[ -n "$CANDIDATE" ]] || {
            echo "ERROR: Set TRACKER_BROWSER_CANDIDATE to a detached candidate worktree."
            echo "For release qualification, use the guarded tracker-release.sh flow."
            exit 2
        }
        CANDIDATE="$(realpath -e -- "$CANDIDATE")"
        [[ "$CANDIDATE" != "$APP" && "$CANDIDATE" != "$APP/"* ]] || {
            echo "ERROR: Refusing to use the installed application as candidate."
            exit 2
        }
        [[ -f "$CANDIDATE/app/main.py" &&
           -f "$CANDIDATE/scripts/tracker-browser-qualify.sh" ]] || {
            echo "ERROR: Invalid detached candidate worktree."
            exit 2
        }
        [[ "$(git -C "$CANDIDATE" rev-parse --show-toplevel)" == "$CANDIDATE" ]] || {
            echo "ERROR: Candidate is not a worktree root."
            exit 2
        }
        exec bash "$CANDIDATE/scripts/tracker-browser-qualify.sh" "$CANDIDATE" "$PY"
        ;;

    *)
        echo "Usage: $0 non-browser|multiuser|browser" >&2
        exit 2
        ;;
esac
