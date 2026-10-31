"""Stage 33.2: isolated browser sorting regressions."""

from pathlib import Path

import pytest
from playwright.sync_api import sync_playwright

pytestmark = pytest.mark.browser

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def page():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context()
        tab = context.new_page()
        errors = []
        tab.on("pageerror", lambda error: errors.append(str(error)))

        yield tab, errors

        context.close()
        browser.close()


def inventory_html():
    headings = [
        ("compound", "Compound"),
        ("vial", "Vial"),
        ("remaining", "Remaining"),
        ("amount", "Amount"),
        ("landed", "Landed"),
        ("cost", "Cost"),
        ("coa", "COA"),
        ("status", "Status"),
    ]

    headers = "".join(
        f'<th data-vial-sort="{key}"><button>{label}</button></th>'
        for key, label in headings
    )

    def row(identifier, compound, remaining):
        return f"""
        <tr>
          <td>
            <input type="checkbox"
                   class="bulk-vial-check"
                   name="vial_ids"
                   value="{identifier}">
          </td>
          <td>{compound}</td>
          <td>Vial {identifier}</td>
          <td>{remaining} mg</td>
          <td>20 mg</td>
          <td>$10</td>
          <td>$12</td>
          <td>Yes</td>
          <td>Sealed</td>
        </tr>
        """

    return f"""
    <table id="tracker-vials-sortable">
      <thead><tr><th>Select</th>{headers}</tr></thead>
      <tbody>
        {row(3, "Zeta", 20)}
        {row(1, "Alpha", 5)}
        {row(2, "Beta", 10)}
      </tbody>
    </table>
    """


def inventory_order(tab):
    return tab.locator(
        "#tracker-vials-sortable tbody "
        ".bulk-vial-check"
    ).evaluate_all(
        "(nodes) => nodes.map(node => node.value)"
    )


def test_inventory_sorting_changes_actual_row_order(page):
    tab, errors = page
    tab.set_content(inventory_html())

    tab.add_script_tag(
        path=str(
            ROOT / "app/static/js/tracker-vials-sort.js"
        )
    )

    compound = tab.locator(
        '[data-vial-sort="compound"] button'
    )

    compound.click()
    assert inventory_order(tab) == ["1", "2", "3"]

    compound.click()
    assert inventory_order(tab) == ["3", "2", "1"]

    remaining = tab.locator(
        '[data-vial-sort="remaining"] button'
    )

    remaining.click()
    assert inventory_order(tab) == ["1", "2", "3"]

    remaining.click()
    assert inventory_order(tab) == ["3", "2", "1"]

    assert not errors, errors


def test_inventory_selection_survives_sorting(page):
    tab, errors = page
    tab.set_content(inventory_html())

    tab.add_script_tag(
        path=str(
            ROOT / "app/static/js/tracker-vials-sort.js"
        )
    )

    selected = tab.locator(
        '.bulk-vial-check[value="2"]'
    )
    selected.check()

    tab.locator(
        '[data-vial-sort="compound"] button'
    ).click()

    assert selected.is_checked()

    tab.locator(
        '[data-vial-sort="remaining"] button'
    ).click()

    assert selected.is_checked()

    assert tab.locator(
        ".bulk-vial-check:checked"
    ).count() == 1

    assert not errors, errors


def workspace_html():
    keys = [
        "compound",
        "vial",
        "status",
        "remaining",
        "first-used",
        "beyond-use",
        "expires",
    ]

    headers = "".join(
        f"""
        <th data-tracker-sort-key="{key}">
          <button>{key}</button>
        </th>
        """
        for key in keys
    )

    def row(identifier, compound, remaining):
        return f"""
        <tr data-tracker-vial-row
            data-tracker-id="{identifier}"
            data-tracker-recommended="0"
            data-tracker-compound="{compound.lower()}"
            data-tracker-vial="vial {identifier}"
            data-tracker-status="sealed"
            data-tracker-remaining="{remaining}"
            data-tracker-first-used=""
            data-tracker-beyond-use=""
            data-tracker-expires="">
          <td>{compound}</td>
          <td>Vial {identifier}</td>
          <td>{remaining}</td>
          <td>
            <a href="/doses/new?vial_id={identifier}">
              Record Dose
            </a>
          </td>
        </tr>
        """

    return f"""
    <input id="tracker-vial-search">
    <button id="tracker-vial-clear">Clear</button>
    <button id="tracker-vial-reset">Reset</button>
    <div id="tracker-vial-count"></div>
    <div id="tracker-vial-no-matches" hidden></div>
    <div id="tracker-available-vials">
      <table data-tracker-sortable-vials>
        <thead><tr>{headers}</tr></thead>
        <tbody>
          {row(3, "Zeta", 20)}
          {row(1, "Alpha", 5)}
          {row(2, "Beta", 10)}
        </tbody>
      </table>
    </div>
    """


def workspace_order(tab):
    return tab.locator(
        "#tracker-available-vials "
        "[data-tracker-vial-row]"
    ).evaluate_all(
        "(nodes) => nodes.map(node => node.dataset.trackerId)"
    )


def test_workspace_sort_search_and_links(page):
    tab, errors = page
    tab.set_content(workspace_html())

    tab.add_script_tag(
        path=str(
            ROOT / "app/static/tracker_dose_workspace.js"
        )
    )

    compound = tab.locator(
        '[data-tracker-sort-key="compound"] button'
    )

    compound.click()
    assert workspace_order(tab) == ["1", "2", "3"]

    compound.click()
    assert workspace_order(tab) == ["3", "2", "1"]

    search = tab.locator("#tracker-vial-search")
    search.fill("Beta")

    visible = tab.locator(
        "#tracker-available-vials "
        "[data-tracker-vial-row]:visible"
    )

    assert visible.count() == 1
    assert visible.first.get_attribute(
        "data-tracker-id"
    ) == "2"

    link = visible.first.locator("a")
    assert link.get_attribute("href") == (
        "/doses/new?vial_id=2"
    )

    search.fill("")

    assert tab.locator(
        "#tracker-available-vials "
        "[data-tracker-vial-row]:visible"
    ).count() == 3

    assert not errors, errors
