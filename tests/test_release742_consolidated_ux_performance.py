"""Release 742: CSS cascade parity, real rendered pages, and bounded reads.

All database fixtures are disposable. Browser checks use rendered app markup,
never live DEV/PROD data or remote origins.
"""
from datetime import date
from pathlib import Path
import re

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from jinja2 import Environment
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app.db import Base, get_db
from app.models import Compound, Page, Purchase, Source
from app.routers import pages, supplies

ROOT = Path(__file__).resolve().parents[1]
CSS = ROOT / "app/static/css"

SUPPLY_SOURCES = (
    "tracker-supply-use-preview.css",
    "tracker-stock-health.css",
    "tracker-stock-filters.css",
)
CALENDAR_SOURCES = (
    "tracker-calendar-views374.css",
    "tracker-calendar-workbench.css",
    "tracker-calendar-dose-mobile369.css",
    "tracker-calendar-day-context.css",
    "tracker-calendar-day-navigation.css",
)


@pytest.fixture
def app_env(tmp_path):
    engine = create_engine(
        "sqlite:///" + str(tmp_path / "tracker742.sqlite"),
        connect_args={"check_same_thread": False},
    )
    @event.listens_for(engine, "connect")
    def enable_foreign_keys(conn, _):
        c = conn.cursor()
        c.execute("PRAGMA foreign_keys=ON")
        c.close()

    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    app = FastAPI()
    app.include_router(supplies.router)
    app.include_router(pages.router)

    def scoped():
        with Session() as db:
            yield db

    app.dependency_overrides[get_db] = scoped
    with TestClient(app, follow_redirects=False) as client:
        yield client, Session, engine
    engine.dispose()


@pytest.mark.parametrize("name, originals, new_path", (
    ("supplies", SUPPLY_SOURCES, "tracker-supplies-bundle742.css"),
    ("calendar", CALENDAR_SOURCES, "tracker-calendar-bundle742.css"),
))
def test_742_css_bundle_preserves_original_order_and_content(name, originals, new_path):
    expected = (
        "/* Release 742 cascade-preserving bundle: " + name.capitalize()
        + ". Historic source files remain unchanged. */\n"
    )
    for original in originals:
        expected += (
            "/* Original source: " + original + " */\n"
            + (CSS / original).read_text().rstrip() + "\n"
        )
    bundled = (CSS / new_path).read_text()
    assert bundled.startswith(expected), new_path
    if name == "calendar":
        assert bundled == expected
    else:
        assert "tracker-ux742-jumps" in bundled[len(expected):]


@pytest.mark.parametrize("template,originals,bundle", (
    ("supplies.html", SUPPLY_SOURCES, "tracker-supplies-bundle742.css"),
    ("calendar.html", CALENDAR_SOURCES, "tracker-calendar-bundle742.css"),
))
def test_742_templates_have_single_css_request_per_bundle(template, originals, bundle):
    html = (ROOT / "app/templates" / template).read_text()
    Environment().parse(html)
    assert html.count("/static/css/" + bundle + "?v=742") == 1
    assert all("/static/css/" + old + "?v=" not in html for old in originals)
    assert "/static/css/tracker-integrated-macd741.css?v=741" in html
    # Existing JS remains in the page; this release only consolidates CSS.
    for old in originals:
        js = old.replace(".css", ".js")
        if (ROOT / "app/static/js" / js).exists():
            assert js in html


def test_742_supplies_finds_recent_purchases_with_bounded_query(app_env):
    client, Session, engine = app_env
    with Session() as db:
        purchases = []
        for i in range(16):
            p = Purchase(vendor="Vendor " + str(i), purchased_on=date(2026, 11, 21))
            db.add(p)
            db.flush()
            purchases.append(p.id)
        db.commit()
    statements = []
    def observe(_conn, _cursor, statement, params, _ctx, _many):
        if "FROM purchases" in statement and "SELECT" in statement:
            statements.append((statement, params))
    event.listen(engine, "before_cursor_execute", observe)
    try:
        response = client.get("/supplies")
    finally:
        event.remove(engine, "before_cursor_execute", observe)
    assert response.status_code == 200
    links = [int(x) for x in re.findall(r'href="/purchases/(\d+)"', response.text)]
    assert links == list(reversed(purchases[-10:]))
    assert statements and all("LIMIT" in statement.upper() for statement, _ in statements)
    for statement, params in statements:
        assert 10 in params, (statement, params)
    for target in ("#tracker-stock-section", "#tracker-supply-category-create",
                   "#tracker-categories", "/reconciliation"):
        assert 'href="' + target + '"' in response.text
    assert response.text.count('id="tracker-supply-category-create"') == 1


def test_742_notes_with_sources_and_compounds_have_bounded_queries(app_env):
    client, Session, engine = app_env
    with Session() as db:
        compound = Compound(name="Fixture compound 742")
        db.add(compound)
        db.flush()
        for i in range(28):
            note = Page(title="Notes 742 " + str(i), body="Source-based notes",
                        tags="testing")
            note.sources = [Source(kind="web", title="Publication " + str(i))]
            if i % 2 == 0:
                note.compounds = [compound]
            db.add(note)
        db.commit()
    sql = []
    def observe(_conn, _cursor, statement, _params, _ctx, _many):
        if statement.lstrip().upper().startswith("SELECT"):
            sql.append(statement)
    event.listen(engine, "before_cursor_execute", observe)
    try:
        response = client.get("/pages?view=with-sources")
    finally:
        event.remove(engine, "before_cursor_execute", observe)
    assert response.status_code == 200
    assert "28 of 28 notes shown" in response.text
    assert "Publication 0" not in response.text  # count, not source titles, on cards
    assert "1 source" in response.text
    assert "Fixture compound 742" in response.text
    assert len(sql) <= 8, "Notes must not generate a query per record: " + str(len(sql))


@pytest.mark.parametrize("width", (320, 390, 430, 760, 1024))
@pytest.mark.parametrize("scheme", ("light", "dark"))
def test_742_rendered_supplies_page_section_jumps_are_accessible(app_env, width, scheme):
    from playwright.sync_api import expect, sync_playwright

    client, _, _ = app_env
    html = client.get("/supplies").text
    # Extract the actual server-rendered navigation from this disposable page.
    nav = re.search(r'<nav class="tracker-ux742-jumps".*?</nav>', html, re.S)
    assert nav
    document = (
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        + nav.group() + '<div id="tracker-stock-section"></div>'
        + '<div id="tracker-supply-category-create"></div>'
        + '<div id="tracker-categories"></div>'
    )
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        try:
            page = browser.new_page(
                viewport={"width": width, "height": 844}, color_scheme=scheme,
            )
            page.set_content(document)
            page.add_style_tag(content=(CSS / "tracker-supplies-bundle742.css").read_text())
            for label in ("Stock & use", "Create category", "Manage categories",
                          "Reconcile stock"):
                link = page.get_by_role("link", name=label)
                expect(link).to_be_visible()
                assert link.evaluate("e => e.getBoundingClientRect().height >= 44")
            page.get_by_role("link", name="Create category").focus()
            assert page.get_by_role("link", name="Create category").evaluate(
                "e => getComputedStyle(e).outlineStyle !== 'none'"
            )
            assert page.evaluate(
                "document.documentElement.scrollWidth <= innerWidth + 1"
            ), (width, scheme)
        finally:
            browser.close()
