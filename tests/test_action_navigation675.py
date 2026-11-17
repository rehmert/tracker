"""Release 675 navigation polish: route retention and mobile presentation."""
from pathlib import Path
import re

from jinja2 import Environment

ROOT = Path(__file__).resolve().parents[1]
T = ROOT / "app/templates"
CSS = ROOT / "app/static/css/tracker-action-nav675.css"
PAGES = (
    "workouts654.html", "workout_quick659.html", "workout_review663.html",
    "workout_analytics660.html", "workout_calendar664.html",
    "workout_program667.html", "quick_entry.html", "purchases.html",
)


def page(name):
    return (T / name).read_text(encoding="utf-8")


def test_675_changed_templates_parse_and_load_shared_mobile_styles():
    for name in PAGES:
        src = page(name)
        Environment().parse(src)
        assert 'tracker-action-nav675.css?v=675' in src, name
        assert src.count('tracker-action-nav675.css?v=675') == 1


def test_675_workout_home_has_named_touch_actions_and_retains_routes():
    src = page("workouts654.html")
    assert '<nav class="ux675-actions" aria-label="Workout shortcuts">' in src
    for endpoint in ("/workouts/quick", "/workouts/analytics",
                     "/workouts/calendar", "/workouts/backfill",
                     "/workouts/insights", "/workouts/routines"):
        assert f'href="{endpoint}"' in src
    assert 'class="ux675-primary workout659-entry-link"' in src
    assert '<details class="ux675-more">' in src
    assert 'action="/workouts/sets"' in src
    assert 'action="/workouts/finish"' in src


def test_675_rapid_gym_preserves_existing_set_writes_and_advanced_links():
    src = page("workout_quick659.html")
    for endpoint in ('/workouts/quick/sets', '/workouts/quick/repeat',
                     '/workouts/quick/finish', '/workouts/insights',
                     '/workouts/calendar', '/workouts/backfill',
                     '/workouts/routines/{{ routine.id }}/plan'):
        assert endpoint in src
    assert 'class="ux675-actions ux675-gym-top"' in src
    assert 'aria-label="Routine tools"' in src
    assert src.count('<summary>More</summary>') >= 2
    assert 'id="workout659-save"' in src
    assert 'id="workout668-queue-set"' in src
    assert 'id="workout674-use-progression"' in src


def test_675_session_review_preserves_data_exports_and_correction_path():
    src = page("workout_review663.html")
    assert 'class="workout663-topnav ux675-actions"' in src
    for endpoint in ('/export.csv', '/export-for-import.csv', '/correct',
                     '/workouts/analytics', '/workouts/insights'):
        assert endpoint in src
    assert 'class="workout663-bottomnav ux675-actions"' in src
    assert 'Volume = load (lb) × reps' in src


def test_675_quick_entry_preserves_all_15_original_fast_destinations():
    src = page("quick_entry.html")
    fast = src.split('<nav class="tracker-quick-fast-paths"', 1)[1].split(
        '</nav>', 1)[0]
    assert fast.count('<a href=') == 15
    assert '<summary>More Actions</summary>' in fast
    assert 'aria-label="Blood pressure">BP</a>' in fast
    assert src.count('data-quick-daily') == 5
    assert 'data-quick-category="all"' in src
    assert 'data-quick-search' in src
    assert src.count('data-quick-action') >= 14


def test_675_purchase_nav_preserves_filters_and_inventory_workflow():
    src = page("purchases.html")
    assert '<nav class="ux675-actions ux-shortcuts"' in src
    for target in ('#new-purchase', '#purchase-history', '/vendor-prices',
                   '/vials', '/supplies', '/inventory-health'):
        assert f'href="{target}"' in src
    assert 'id="purchase-history-table"' in src
    assert 'data-purchase-search' in src
    assert 'action="/purchases"' in src


def test_675_css_supports_small_phones_keyboard_and_hidden_secondary_links():
    css = CSS.read_text()
    assert '@media(max-width:760px)' in css
    assert '@media(max-width:350px)' in css
    assert 'min-height:44px' in css
    assert ':focus-visible' in css
    assert '.ux675-more[open]' in css
    assert 'grid-template-columns:repeat(2,minmax(0,1fr))' in css
    assert css.count('{') == css.count('}')


def test_675_abbreviations_do_not_remove_explanations_of_critical_actions():
    home = page("workouts654.html")
    quick = page("workout_quick659.html")
    purchases = page("purchases.html")
    assert "Log completed sets only" in home
    assert "Drafts stay on this device; they are not logged." in quick
    assert "An order alone adds no stock." in purchases
    for name in PAGES:
        assert re.search(r'<a\\b', page(name))
