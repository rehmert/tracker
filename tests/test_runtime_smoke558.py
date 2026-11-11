"""Release 558: reject encoded URL delimiters in sidebar paths."""

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/tracker-runtime-smoke.py"


@pytest.fixture
def smoke():
    spec = importlib.util.spec_from_file_location(
        "tracker_smoke558", SCRIPT
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def parse(smoke, url):
    parser = smoke.Links()
    parser.feed(
        '<nav id="app-sidebar">'
        f'<a href="{url}">Link</a>'
        '</nav>'
    )
    parser.close()
    smoke.validate_sidebar_structure(parser)
    return parser


@pytest.mark.parametrize(
    "url,expected",
    [
        ("/vials", "/vials"),
        ("/labs/history", "/labs/history"),
        ("/reports/v1.2", "/reports/v1.2"),
        ("/items%20archived", "/items%20archived"),
        ("/caf%C3%A9", "/caf%C3%A9"),
        ("/reports/%2520archive", "/reports/%2520archive"),
        ("/vials?sort=name", "/vials"),
        ("/vials#inventory", "/vials"),
        ("/vials?sort=name#top", "/vials"),
        ("/vials?sort=a%23b", "/vials"),
    ],
)
def test_valid_urls_preserved558(smoke, url, expected):
    assert parse(smoke, url).paths == [expected]


@pytest.mark.parametrize(
    "url",
    [
        "/reports/%3fmode=1",
        "/reports/%3Fmode=1",
        "/reports/%23section",
        "/reports/%23Section",
        "/reports/name%3fother",
        "/reports/name%23fragment",
    ],
)
def test_encoded_delimiters_rejected558(smoke, url):
    with pytest.raises(
        ValueError,
        match="Sidebar URL contains encoded delimiters",
    ):
        parse(smoke, url)


@pytest.mark.parametrize(
    "url",
    [
        "/reports/%253fmode",
        "/reports/%253Fmode",
        "/reports/%2523section",
        "/reports/%25253fmode",
        "/reports/%252523section",
        "/reports/%2525253fmode",
    ],
)
def test_nested_delimiters_rejected558(smoke, url):
    with pytest.raises(
        ValueError,
        match="nested encoded unsafe path",
    ):
        parse(smoke, url)


@pytest.mark.parametrize(
    "url,expected",
    [
        (
            "/reports/%252e%252e/vials",
            "nested encoded unsafe path",
        ),
        (
            "/reports/%252f/vials",
            "nested encoded unsafe path",
        ),
        (
            "/reports/%250a/vials",
            "nested encoded unsafe path",
        ),
        (
            "/reports/../vials",
            "dot path segments",
        ),
        (
            "/reports/%2e%2e/vials",
            "dot path segments",
        ),
        (
            "/reports//vials",
            "ambiguous separators",
        ),
        (
            "/reports%5cvials",
            "backslash separators",
        ),
        (
            "/vials%",
            "malformed percent encoding",
        ),
        (
            "/vials%00",
            "encoded control characters",
        ),
    ],
)
def test_previous_url_guards_preserved558(
    smoke, url, expected
):
    with pytest.raises(ValueError, match=expected):
        parse(smoke, url)


def test_attribute_integrity_preserved558(smoke):
    parser = smoke.Links()

    with pytest.raises(
        ValueError,
        match="Ambiguous sidebar link href attributes",
    ):
        parser.feed(
            '<nav id="app-sidebar">'
            '<a href="/vials" href="/labs">Link</a>'
            '</nav>'
        )


def test_duplicate_sidebar_rejected558(smoke):
    parser = smoke.Links()
    parser.feed(
        '<nav id="app-sidebar"></nav>'
        '<nav id="app-sidebar"></nav>'
    )
    parser.close()

    with pytest.raises(ValueError, match="found 2"):
        smoke.validate_sidebar_structure(parser)


def test_sidebar_coverage_preserved558(smoke):
    parser = smoke.Links()
    parser.feed(
        '<nav id="app-sidebar">'
        + "".join(
            f'<a href="/page-{i}">Page</a>'
            for i in range(51)
        )
        + '</nav>'
    )
    parser.close()

    smoke.validate_sidebar_structure(parser)

    with pytest.raises(ValueError, match="51/52"):
        smoke.validate_sidebar_coverage(parser.paths)


def test_prior_smoke_protections_preserved558():
    source = SCRIPT.read_text()

    for marker in (
        "validate_health_response(health)",
        "validate_dashboard_identity(dashboard, instance)",
        "validate_sidebar_structure(parser)",
        "validate_sidebar_coverage(paths)",
        "validate_sidebar_path(parsed.path)",
        "response.read(MAX_RESPONSE_BYTES + 1)",
        "if len(body) > MAX_RESPONSE_BYTES:",
        "Authenticated sidebar rejected: ",
        "auth.revoke(token)",
        "if len(declarations) != 1",
        "urllib.parse.urlsplit(url)",
        "parser.close()",
    ):
        assert marker in source, marker
