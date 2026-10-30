
import os

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
        '#app-sidebar > .nav-pinned'
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
        ...document.querySelector('#app-sidebar').children
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

        assert names == sorted(
            names,
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
