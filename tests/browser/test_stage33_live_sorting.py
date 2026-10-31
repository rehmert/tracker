"""Stage 33.3: read-only tests against the running Tracker UI."""

import os

import pytest
from playwright.sync_api import sync_playwright

BASE_URL = os.environ.get(
    "TRACKER_TEST_URL", "http://127.0.0.1:8000"
).rstrip("/")


@pytest.fixture(scope="module")
def browser():
    with sync_playwright() as playwright:
        instance = playwright.chromium.launch(headless=True)
        yield instance
        instance.close()


@pytest.fixture
def page(browser):
    options = {"viewport": {"width": 1440, "height": 900}}

    username = os.environ.get("TRACKER_TEST_USER")
    password = os.environ.get("TRACKER_TEST_PASSWORD")

    if username is not None and password is not None:
        options["http_credentials"] = {
            "username": username,
            "password": password,
        }

    context = browser.new_context(**options)
    tab = context.new_page()
    errors = []

    tab.on("pageerror", lambda error: errors.append(str(error)))

    yield tab, errors

    context.close()


def navigate(tab, path):
    response = tab.goto(
        BASE_URL + path,
        wait_until="networkidle",
        timeout=30000,
    )
    assert response is not None
    assert response.status == 200, (
        f"{path} returned HTTP {response.status}"
    )


def row_ids(tab, selector):
    return tab.locator(selector).evaluate_all("""
        rows => rows.map(row => (
            row.dataset.trackerId ||
            row.querySelector('input[name="vial_ids"]')?.value ||
            row.textContent.trim()
        ))
    """)


def test_live_vials_sorting(page):
    tab, errors = page
    navigate(tab, "/vials")

    table = tab.locator("#tracker-vials-sortable")
    assert table.count() == 1

    heading = table.locator(
        '[data-vial-sort="compound"]'
    )
    assert heading.count() == 1

    rows = "#tracker-vials-sortable tbody tr"
    count = tab.locator(rows).count()

    if count < 2:
        pytest.skip("Fewer than two inventory rows")

    heading.click()
    ascending = row_ids(tab, rows)

    heading.click()
    descending = row_ids(tab, rows)

    assert sorted(ascending) == sorted(descending)

    compounds = tab.locator(rows).evaluate_all("""
        rows => rows.map(row =>
            row.querySelectorAll('td')[1]?.textContent.trim()
        )
    """)

    if len(set(compounds)) > 1:
        assert ascending != descending, (
            "Sorting did not change inventory row order"
        )

    assert not errors, "\n".join(errors)


def test_live_vials_selection_survives_sort(page):
    tab, errors = page
    navigate(tab, "/vials")

    table = tab.locator("#tracker-vials-sortable")
    checkboxes = table.locator(
        'tbody input[type="checkbox"][name="vial_ids"]'
    )

    if checkboxes.count() < 2:
        pytest.skip("Fewer than two selectable inventory rows")

    selected = checkboxes.first
    selected_id = selected.get_attribute("value")
    assert selected_id is not None

    selected.check()

    table.locator(
        '[data-vial-sort="compound"]'
    ).click()

    retained = table.locator(
        f'tbody input[name="vial_ids"][value="{selected_id}"]'
    )

    assert retained.is_checked()
    assert not errors, "\n".join(errors)


def test_live_workspace_sorting(page):
    tab, errors = page
    navigate(tab, "/dose-workspace")

    container = tab.locator("#tracker-available-vials")
    assert container.count() == 1

    rows = (
        "#tracker-available-vials "
        "[data-tracker-vial-row]"
    )

    if tab.locator(rows).count() < 2:
        pytest.skip("Fewer than two workspace vials")

    heading = container.locator(
        '[data-tracker-sort-key="compound"]'
    )
    assert heading.count() == 1

    heading.click()
    ascending = row_ids(tab, rows)

    heading.click()
    descending = row_ids(tab, rows)

    assert sorted(ascending) == sorted(descending)

    compounds = tab.locator(rows).evaluate_all("""
        rows => rows.map(row => row.dataset.trackerCompound)
    """)

    if len(set(compounds)) > 1:
        assert ascending != descending, (
            "Workspace sorting did not change row order"
        )

    assert not errors, "\n".join(errors)


def test_live_workspace_search(page):
    tab, errors = page
    navigate(tab, "/dose-workspace")

    search = tab.locator("#tracker-vial-search")
    assert search.count() == 1

    rows = tab.locator(
        "#tracker-available-vials "
        "[data-tracker-vial-row]"
    )

    if rows.count() == 0:
        pytest.skip("No workspace vials available")

    search.fill("stage33-no-match-987654321")

    assert rows.locator("visible=true").count() == 0

    search.fill("")

    assert rows.locator("visible=true").count() == rows.count()

    assert not errors, "\n".join(errors)
