"""Regression contracts for saved PK scenario dose pagination."""
from pathlib import Path

from jinja2 import Environment

ROOT = Path(__file__).resolve().parents[1]


def read(name):
    return (ROOT / name).read_text()


def test_pagination_controls_exist():
    html = read("app/templates/pk.html")

    for id_ in (
        "pkPlannedPageSize",
        "pkPlannedPageStatus",
        "pkPlannedPageNumber",
        "pkPlannedPrev",
        "pkPlannedNext",
        "plannedRows",
    ):
        assert f'id="{id_}"' in html

    assert '<option value="5" selected>5</option>' in html

    assert (
        "tracker-pk-planned-pagination.css?v=batch109"
        in html
    )

    Environment().parse(html)


def test_page_sizes_and_navigation():
    js = read("app/static/pk.js")

    assert "let plannedPage = 0" in js
    assert "lastRenderedScenarioId" in js
    assert "Math.ceil(all.length / 25) * 25" in js
    assert "size += 25" in js
    assert "all.slice(offset, offset + pageSize)" in js

    assert "'pkPlannedPageSize'" in js
    assert "'pkPlannedPrev'" in js
    assert "'pkPlannedNext'" in js

    assert "plannedPage = 0;" in js
    assert "pageCount - 1" in js


def test_edit_and_delete_remain_available():
    js = read("app/static/pk.js")

    assert "for (const d of shown)" in js

    assert (
        "d.id}`,'PUT'"
        in js
    )

    assert (
        "d.id}`,'DELETE'"
        in js
    )


def test_existing_pk_scenario_api_preserved():
    routes = read("app/routers/pk.py")

    for route in (
        '@router.get("/scenarios")',
        '@router.post("/scenarios", status_code=201)',
        '@router.put("/scenarios/{sid}")',
        '@router.delete("/scenarios/{sid}")',
    ):
        assert route in routes
