
"""Stage 10: browser regression tests for bulk vial selections."""

import re
from pathlib import Path

import pytest
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "app/templates/vials.html"

SCRIPT_MARKER = "/* TRACKER_BULK_STAGE9 */"


def selection_script():
    source = TEMPLATE.read_text()
    start = source.index(SCRIPT_MARKER)
    end = source.index("</script>", start)
    return source[start:end]


def html_fixture():
    return """
<!doctype html>
<html>
<body>

<form id="bulk-vials">

<table>
<thead>
<tr>
<th><input type="checkbox" id="bulk-all"></th>
</tr>
</thead>
<tbody>

<tr>
<td><input type="checkbox" class="bulk-vial-check"
           name="vial_ids" value="1"></td>
<td>Compound A</td>
<td><a>Vial A1</a></td>
<td></td><td></td><td></td><td></td><td></td>
<td>Sealed</td>
</tr>

<tr>
<td><input type="checkbox" class="bulk-vial-check"
           name="vial_ids" value="2"></td>
<td>Compound A</td>
<td><a>Vial A2</a></td>
<td></td><td></td><td></td><td></td><td></td>
<td>In use</td>
</tr>

<tr>
<td><input type="checkbox" class="bulk-vial-check"
           name="vial_ids" value="3"></td>
<td>Compound B</td>
<td><a>Vial B1</a></td>
<td></td><td></td><td></td><td></td><td></td>
<td>Sealed</td>
</tr>

</tbody>
</table>

<button type="submit">Update</button>
</form>

<div id="bulk-selection-tools">
<div class="inline">

<select id="bulk7-compound">
<option value="">All compounds</option>
</select>

<select id="bulk7-status">
<option value="">All statuses</option>
<option value="sealed">Sealed</option>
<option value="in_use">In use</option>
</select>

<button id="bulk7-select">Select matching</button>
<button id="bulk7-invert">Invert selection</button>
<button id="bulk7-clear">Clear visible</button>
<button id="bulk7-export">Export selected CSV</button>

</div>
<p id="bulk7-summary"></p>
</div>

<span id="bulk-count"></span>

</body>
</html>
"""


@pytest.fixture
def page():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            headless=True
        )

        context = browser.new_context(
            accept_downloads=True
        )

        page = context.new_page()

        # HTTP origin allows sessionStorage.
        page.route(
            "http://tracker-stage10.test/*",
            lambda route: route.fulfill(
                status=200,
                content_type="text/html",
                body=html_fixture(),
            ),
        )

        page.goto(
            "http://tracker-stage10.test/vials"
        )

        page.add_script_tag(
            content=selection_script()
        )

        yield page

        context.close()
        browser.close()


def selected_ids(page):
    return page.locator(
        ".bulk-vial-check:checked"
    ).evaluate_all(
        "(nodes) => nodes.map(node => node.value)"
    )


def stored_ids(page):
    return page.evaluate("""() => {
        const value = JSON.parse(
            sessionStorage.getItem(
                "tracker.bulkVials.selection.v1"
            ) || "{}"
        );
        return Object.keys(value);
    }""")


def test_select_matching_compound(page):
    page.select_option(
        "#bulk7-compound",
        "Compound A"
    )

    page.click("#bulk7-select")

    assert selected_ids(page) == ["1", "2"]
    assert stored_ids(page) == ["1", "2"]


def test_select_matching_status(page):
    page.select_option(
        "#bulk7-status",
        "sealed"
    )

    page.click("#bulk7-select")

    assert selected_ids(page) == ["1", "3"]


def test_invert_selection(page):
    page.locator(
        '.bulk-vial-check[value="1"]'
    ).check()

    page.click("#bulk7-invert")

    assert selected_ids(page) == ["2", "3"]


def test_clear_visible(page):
    page.click("#bulk7-select")

    assert len(selected_ids(page)) == 3

    page.click("#bulk7-clear")

    assert selected_ids(page) == []
    assert stored_ids(page) == []


def test_clear_all(page):
    page.click("#bulk7-select")

    page.click("#bulk8-clear-all")

    assert selected_ids(page) == []
    assert stored_ids(page) == []


def test_selection_summary(page):
    page.click("#bulk7-select")

    assert "3 selected" in page.locator(
        "#bulk7-summary"
    ).inner_text()


def test_selection_survives_page_reload(page):
    page.locator(
        '.bulk-vial-check[value="1"]'
    ).check()

    assert stored_ids(page) == ["1"]

    page.reload()
    page.add_script_tag(
        content=selection_script()
    )

    assert selected_ids(page) == ["1"]


def test_hidden_cross_view_selection(page):
    page.evaluate("""() => {
        sessionStorage.setItem(
            "tracker.bulkVials.selection.v1",
            JSON.stringify({
                "99": {
                    id: "99",
                    compound: "Compound C",
                    label: "Vial C1",
                    status: "sealed"
                }
            })
        );
    }""")

    page.reload()
    page.add_script_tag(
        content=selection_script()
    )

    hidden = page.locator(
        'input[data-bulk8-hidden="1"]'
    )

    assert hidden.count() == 1
    assert hidden.input_value() == "99"


def test_export_selected_csv(page):
    page.click("#bulk7-select")

    with page.expect_download() as download_info:
        page.click("#bulk7-export")

    download = download_info.value

    assert download.suggested_filename == (
        "tracker-selected-vials.csv"
    )

    content = Path(download.path()).read_text(
        encoding="utf-8-sig"
    )

    assert "Compound A" in content
    assert "Compound B" in content
    assert "Vial A1" in content


def test_selection_limit(page):
    page.evaluate("""() => {
        const selection = {};

        for (let id = 1001; id <= 2000; id++) {
            selection[String(id)] = {
                id: String(id),
                compound: "Other",
                label: "Saved",
                status: "sealed"
            };
        }

        sessionStorage.setItem(
            "tracker.bulkVials.selection.v1",
            JSON.stringify(selection)
        );
    }""")

    page.reload()
    page.add_script_tag(
        content=selection_script()
    )

    page.on("dialog", lambda dialog: dialog.accept())

    page.click("#bulk7-select")

    assert len(stored_ids(page)) == 1000
    assert selected_ids(page) == []
