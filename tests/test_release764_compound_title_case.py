"""Release 764: user-defined compound names exempt whole titles from Title Case.

Synthetic, disposable DB and Node VM: no network or live inventory access.
"""
import json
import subprocess
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.db import Base
from app.models import Compound
from app.routers.compounds import compound_title_names
from app.templating import templates

ROOT = Path(__file__).resolve().parents[1]
JS_PATH = ROOT / "app/static/js/tracker-page-title-case.js"


@pytest.fixture
def db():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    engine.dispose()


def test_764_compound_names_are_exact_and_response_is_private(db):
    db.add_all([
        Compound(name="BPC-157", category="peptide"),
        Compound(name="Test C", category="testosterone"),
        Compound(name="iPamorelin", category="peptide"),
    ])
    db.flush()
    response = compound_title_names(db=db)
    assert response.headers["cache-control"] == "private, no-store"
    assert json.loads(response.body) == {
        "names": ["BPC-157", "Test C", "iPamorelin"]
    }
    assert not db.dirty and not db.deleted


def test_764_route_uses_scoped_db_dependency():
    from fastapi.routing import APIRoute
    from app.routers.compounds import router
    from app.scoped_db390 import get_scoped_db390

    route = next(route for route in router.routes if isinstance(route, APIRoute)
                 and route.path == "/compounds/title-names")
    assert "GET" in route.methods
    assert any(dep.call is get_scoped_db390
               for dep in route.dependant.dependencies)


@pytest.mark.parametrize("title,heading,names,expected_title,expected_heading", [
    (
        "bpc-157 injection tracking · tracker", "bpc-157 injection tracking",
        ["BPC-157", "Test C"],
        "bpc-157 injection tracking · tracker", "bpc-157 injection tracking",
    ),
    (
        "test c injections · tracker", "test c injections",
        ["Test C"],
        "test c injections · tracker", "test c injections",
    ),
    (
        "iPamorelin cycle · tracker", "iPamorelin cycle",
        ["iPamorelin"],
        "iPamorelin cycle · tracker", "iPamorelin cycle",
    ),
    (
        "testing units · tracker", "testing units",
        ["Test"],
        "Testing Units · Tracker", "Testing Units",
    ),
    (
        "day 7 schedule · tracker", "day 7 schedule",
        ["BPC-157", "Test C"],
        "Day 7 Schedule · Tracker", "Day 7 Schedule",
    ),
])
def test_764_browser_titles_and_headings(
    title, heading, names, expected_title, expected_heading
):
    script = r"""
const fs = require('fs');
const vm = require('vm');
const input = JSON.parse(process.argv[1]);
const code = fs.readFileSync(process.argv[2], 'utf8');
const node = {nodeValue: input.heading, parentElement: {closest: () => null}};
const heading = {
  closest: () => null,
  get textContent() { return node.nodeValue; }
};
const main = {contains: () => true, querySelectorAll: () => [heading]};
const document = {
  title: input.title,
  readyState: 'complete',
  getElementById: (id) => id === 'main-content' ? main : null,
  addEventListener: () => {},
  createTreeWalker: () => {
    let emitted = false;
    return {
      currentNode: node,
      nextNode: () => {
        if (emitted) return false;
        emitted = true;
        return true;
      }
    };
  }
};
const sandbox = {
  document,
  Node: { ELEMENT_NODE: 1 },
  NodeFilter: { SHOW_TEXT: 4, FILTER_REJECT: 2, FILTER_ACCEPT: 1 },
  requestAnimationFrame: (cb) => cb(),
  MutationObserver: function () { this.observe = () => {}; },
  fetch: (url, options) => {
    if (url !== '/compounds/title-names' ||
        options.credentials !== 'same-origin' ||
        options.cache !== 'no-store') {
      throw Error('Unexpected catalog request');
    }
    return Promise.resolve({
      ok: true,
      json: () => Promise.resolve({names: input.names})
    });
  }
};
vm.runInNewContext(code, sandbox);
setImmediate(() => process.stdout.write(JSON.stringify({
  title: document.title, heading: node.nodeValue
})));
"""
    result = subprocess.run(
        ["node", "-e", script, json.dumps({
            "title": title, "heading": heading, "names": names,
        }), str(JS_PATH)],
        check=True, capture_output=True, text=True, timeout=10,
    )
    assert json.loads(result.stdout) == {
        "title": expected_title, "heading": expected_heading,
    }


def test_764_catalog_failure_does_not_change_title():
    script = r"""
const fs = require('fs');
const vm = require('vm');
const document = {
  title: 'test c monitoring · tracker', readyState: 'complete',
  getElementById: () => null, addEventListener: () => {}
};
vm.runInNewContext(fs.readFileSync(process.argv[1], 'utf8'), {
  document, fetch: () => Promise.reject(Error('offline'))
});
setImmediate(() => process.stdout.write(document.title));
"""
    result = subprocess.run(
        ["node", "-e", script, str(JS_PATH)],
        check=True, capture_output=True, text=True, timeout=10,
    )
    assert result.stdout == "test c monitoring · tracker"


def test_764_assets_and_opt_outs_are_preserved():
    base = (ROOT / "app/templates/base.html").read_text()
    js = JS_PATH.read_text()
    assert base.count("tracker-page-title-case.js") == 1
    assert "tracker-page-title-case.js?v=798" in base
    assert 'isCompoundTitle(element.textContent || "")' in js
    assert 'document.title && !isCompoundTitle(document.title)' in js
    assert "htmx:afterSwap" in js
    assert "data-no-title-case" in js
    templates.env.get_template("base.html")
