
import os
import re

import pytest

playwright = pytest.importorskip(
    "playwright.sync_api",
    reason="Playwright is required for browser tests",
)

from playwright.sync_api import sync_playwright


BASE_URL = os.environ.get(
    "TRACKER_TEST_URL",
    "http://127.0.0.1:8000",
).rstrip("/")


@pytest.fixture(scope="module")
def browser():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        yield browser
        browser.close()


@pytest.fixture
def page(browser):
    context_options = {
        "viewport": {"width": 1440, "height": 900},
    }

    username = os.environ.get("TRACKER_TEST_USER")
    password = os.environ.get("TRACKER_TEST_PASSWORD")

    if username is not None and password is not None:
        context_options["http_credentials"] = {
            "username": username,
            "password": password,
        }

    context = browser.new_context(**context_options)

    # Each test receives a fresh browser context.
    page = context.new_page()

    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))

    response = page.goto(
        BASE_URL + "/",
        wait_until="networkidle",
        timeout=30000,
    )

    assert response is not None
    assert response.status == 200

    page.locator("#nav-sortable .nav-section").first.wait_for()

    yield page, errors

    context.close()


def test_no_javascript_errors(page):
    tab, errors = page
    assert not errors, "\n".join(errors)


def test_dashboard_above_favorites(page):
    tab, _ = page

    result = tab.evaluate("""
    () => {
      const dashboard = document.querySelector(
        '#app-sidebar .nav-scroll > .nav-pinned'
      );
      const favorites = document.querySelector(
        '#nav-favorites'
      );
      const categories = document.querySelector(
        '#nav-sortable'
      );

      if (!dashboard || !favorites || !categories) {
        return false;
      }

      const nodes = [
        ...document.querySelector('#app-sidebar .nav-scroll').children
      ];

      return (
        nodes.indexOf(dashboard) < nodes.indexOf(favorites)
        && nodes.indexOf(favorites) < nodes.indexOf(categories)
      );
    }
    """)

    assert result


def test_dashboard_not_duplicated(page):
    tab, _ = page

    assert tab.locator(
        ".nav-pinned [data-nav-key='/']"
    ).count() == 1

    assert tab.locator(
        ".nav-pinned .nav-star"
    ).count() == 0


def test_categories_alphabetical(page):
    tab, _ = page

    names = tab.locator(
        "#nav-sortable > .nav-section"
    ).evaluate_all("""
    elements => elements.map(
      element => element.dataset.section
    )
    """)

    expected = sorted(names, key=str.casefold)

    assert names == expected


def test_category_expands_and_collapses(page):
    tab, errors = page

    button = tab.locator(
        "#nav-sortable .nav-section-toggle"
    ).first

    before = button.get_attribute("aria-expanded")

    button.click()

    after = button.get_attribute("aria-expanded")

    assert before != after

    button.click()

    assert button.get_attribute("aria-expanded") == before
    assert not errors, "\n".join(errors)


def test_category_state_survives_refresh(page):
    tab, _ = page

    button = tab.locator(
        "#nav-sortable .nav-section-toggle"
    ).first

    if button.get_attribute("aria-expanded") != "true":
        button.click()

    assert button.get_attribute("aria-expanded") == "true"

    tab.reload(wait_until="networkidle")

    button = tab.locator(
        "#nav-sortable .nav-section-toggle"
    ).first

    assert button.get_attribute("aria-expanded") == "true"


def test_header_page_finder(page):
    tab, errors = page

    finder = tab.locator("#nav-filter")
    results = tab.locator("#page-finder-results")

    assert finder.is_visible()

    finder.fill("calendar")

    assert results.is_visible()
    assert results.locator(
        "a[href='/calendar']"
    ).count() >= 1

    assert not errors, "\n".join(errors)


def test_page_finder_keyboard(page):
    tab, _ = page

    finder = tab.locator("#nav-filter")
    finder.fill("calendar")

    finder.press("ArrowDown")

    selected = tab.locator(
        "#page-finder-results [aria-selected='true']"
    )

    assert selected.count() == 1

    finder.press("Escape")

    assert tab.locator(
        "#page-finder-results"
    ).is_hidden()


def test_page_finder_no_matches(page):
    tab, _ = page

    finder = tab.locator("#nav-filter")

    finder.fill("unlikely-page-xyz-98765")

    assert tab.locator(
        "#page-finder-results"
    ).is_visible()

    assert "No matching pages" in tab.locator(
        "#page-finder-results"
    ).inner_text()


def test_page_links_alphabetical(page):
    tab, _ = page

    sections = tab.locator(
        "#nav-sortable > .nav-section"
    )

    for index in range(sections.count()):
        section = sections.nth(index)

        names = section.locator(
            ".nav-group > li > a"
        ).all_inner_texts()

        normalized = [name.strip() for name in names]
        assert normalized == sorted(
            normalized,
            key=str.casefold,
        )


def test_search_tracker_opens(page):
    tab, errors = page

    tab.locator("#command-open").click()

    assert tab.locator(
        "#command-overlay"
    ).is_visible()

    assert tab.locator(
        "#command-input"
    ).is_visible()

    assert not errors, "\n".join(errors)


def test_favorites_container_exists(page):
    tab, _ = page

    assert tab.locator("#nav-favorites").count() == 1
    assert tab.locator("#nav-favorite-links").count() == 1


def test_navigation_preferences_exist(page):
    tab, _ = page

    assert tab.locator("#nav-sort-mode").count() == 1
    assert tab.locator("#nav-edit-toggle").count() == 1
    assert tab.locator("#nav-reset").count() == 1


def test_dose_566_vial_ids_and_time_controls_at_desktop_and_mobile(page):
    """Real Chromium layout, read-only; no dose is submitted."""
    tab, errors = page
    response = tab.goto(BASE_URL + "/doses", wait_until="networkidle", timeout=30000)
    assert response is not None and response.status == 200

    chooser = tab.locator('form[hx-post="/doses"] select[name="vial_id"]')
    chooser.wait_for()
    options = chooser.locator("option").all_inner_texts()
    assert options, "The isolated candidate should have disposable vials."
    assert all(re.search(r"\s#\d+", label) for label in options), options

    form = tab.locator('form[hx-post="/doses"]')
    original = form.locator('input[name="taken_at"]')
    date = form.locator(".tracker-time24-date")
    clock = form.locator(".tracker-time24-clock")
    now = form.locator(".tracker-time24-now")
    now.wait_for()

    for width in (1440, 800, 390):
        tab.set_viewport_size({"width": width, "height": 900})
        box_date = date.bounding_box()
        box_clock = clock.bounding_box()
        box_now = now.bounding_box()
        assert box_date and box_clock and box_now
        if width > 720:
            assert box_date["x"] + box_date["width"] <= box_clock["x"] + 2
            assert box_clock["x"] + box_clock["width"] <= box_now["x"] + 2
        else:
            assert box_date["x"] + box_date["width"] <= box_clock["x"] + 2
            assert box_now["y"] >= max(
                box_date["y"] + box_date["height"],
                box_clock["y"] + box_clock["height"],
            ) - 2
        assert box_now["x"] + box_now["width"] <= width + 1

    now.click()
    assert re.fullmatch(
        r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}",
        original.input_value(),
    )
    assert not errors, "\n".join(errors)
