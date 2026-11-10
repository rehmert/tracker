"""Release 544: nesting-aware authenticated sidebar discovery."""

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/tracker-runtime-smoke.py"


@pytest.fixture
def smoke():
    spec = importlib.util.spec_from_file_location(
        "tracker_smoke544", SCRIPT
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def parse(smoke, html):
    parser = smoke.Links()
    parser.feed(html)
    parser.close()
    return parser


def test_nested_nav_does_not_end_sidebar544(smoke):
    parser = parse(
        smoke,
        '''
        <nav id="app-sidebar">
          <a href="/first">First</a>
          <nav>
            <a href="/nested">Nested</a>
          </nav>
          <a href="/after-nested">After</a>
        </nav>
        <a href="/outside">Outside</a>
        ''',
    )

    assert parser.paths == [
        "/first",
        "/nested",
        "/after-nested",
    ]
    assert parser.sidebar_depth == 0


def test_multiple_nested_levels544(smoke):
    parser = parse(
        smoke,
        '''
        <nav id="app-sidebar">
          <nav>
            <nav>
              <a href="/deep">Deep</a>
            </nav>
            <a href="/middle">Middle</a>
          </nav>
          <a href="/outer">Outer</a>
        </nav>
        <a href="/outside">Outside</a>
        ''',
    )

    assert parser.paths == [
        "/deep",
        "/middle",
        "/outer",
    ]


def test_non_sidebar_nav_is_ignored544(smoke):
    parser = parse(
        smoke,
        '''
        <nav id="other-nav">
          <a href="/ignore">Ignore</a>
        </nav>
        <nav id="app-sidebar">
          <a href="/include">Include</a>
        </nav>
        ''',
    )

    assert parser.paths == ["/include"]


def test_relative_and_external_links_ignored544(smoke):
    parser = parse(
        smoke,
        '''
        <nav id="app-sidebar">
          <a href="relative">Relative</a>
          <a href="//external.example/path">External</a>
          <a href="https://external.example">External</a>
          <a href="/local">Local</a>
        </nav>
        ''',
    )

    assert parser.paths == ["/local"]


def test_query_stripping_preserved544(smoke):
    parser = parse(
        smoke,
        '''
        <nav id="app-sidebar">
          <a href="/labs?page=2">Labs</a>
          <a href="/labs?page=3">Labs again</a>
          <a href="/vitals">Vitals</a>
        </nav>
        ''',
    )

    assert parser.paths == [
        "/labs",
        "/labs",
        "/vitals",
    ]

    assert list(dict.fromkeys(parser.paths)) == [
        "/labs",
        "/vitals",
    ]


def test_missing_href_does_not_crash544(smoke):
    parser = parse(
        smoke,
        '''
        <nav id="app-sidebar">
          <a>Missing</a>
          <a href="">Empty</a>
          <a href="/valid">Valid</a>
        </nav>
        ''',
    )

    assert parser.paths == ["/valid"]


def test_nested_sidebar_inside_other_nav544(smoke):
    parser = parse(
        smoke,
        '''
        <nav id="outer">
          <a href="/ignore">Ignore</a>
          <nav id="app-sidebar">
            <a href="/include">Include</a>
          </nav>
          <a href="/ignore-again">Ignore</a>
        </nav>
        ''',
    )

    assert parser.paths == ["/include"]
    assert parser.sidebar_depth == 0


def test_smoke_security_behaviors_preserved544():
    source = SCRIPT.read_text()

    for marker in (
        "AUTH_REDIRECT HTTP",
        "AUTH_REJECTED HTTP",
        "auth.revoke(token)",
        "SIDEBAR_FAILURES=",
        "service_working_directory()",
        '"TRANSPORT " + category',
    ):
        assert marker in source
