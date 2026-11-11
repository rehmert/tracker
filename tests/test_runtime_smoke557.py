"""Release 557: nested percent-encoding path safety."""

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/tracker-runtime-smoke.py"


@pytest.fixture
def smoke():
    spec = importlib.util.spec_from_file_location(
        "tracker_smoke557", SCRIPT
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
        ("/vials?sort=name#top", "/vials"),
        ("/vials/item..backup", "/vials/item..backup"),
    ],
)
def test_valid_paths_preserved557(smoke, url, expected):
    assert parse(smoke, url).paths == [expected]


@pytest.mark.parametrize(
    "url",
    [
        "/reports/%252e%252e/vials",
        "/reports/%252E%252E/vials",
        "/reports/%252e/vials",
        "/reports/%252e%252e%252fvials",
        "/reports/%252f/vials",
        "/reports/%255c/vials",
        "/reports/%250a/vials",
        "/reports/%257f/vials",
        "/reports/%25252e%25252e/vials",
        "/reports/%2525252e%2525252e/vials",
    ],
)
def test_nested_unsafe_encoding_rejected557(
    smoke, url
):
    with pytest.raises(
        ValueError,
        match="nested encoded unsafe path",
    ):
        parse(smoke, url)


@pytest.mark.parametrize(
    "url,expected",
    [
        ("/reports/../vials", "dot path segments"),
        ("/reports/%2e%2e/vials", "dot path segments"),
        ("/reports//vials", "ambiguous separators"),
        ("/reports/%2f/vials", "ambiguous separators"),
        ("/reports%5cvials", "backslash separators"),
        ("/vials%", "malformed percent encoding"),
        ("/vials%00", "encoded control characters"),
    ],
)
def test_release556_guards_preserved557(
    smoke, url, expected
):
    with pytest.raises(ValueError, match=expected):
        parse(smoke, url)


def test_duplicate_href_guard_preserved557(smoke):
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


def test_duplicate_sidebar_guard_preserved557(smoke):
    parser = smoke.Links()
    parser.feed(
        '<nav id="app-sidebar"></nav>'
        '<nav id="app-sidebar"></nav>'
    )
    parser.close()

    with pytest.raises(ValueError, match="found 2"):
        smoke.validate_sidebar_structure(parser)


def test_coverage_guard_preserved557(smoke):
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


def test_prior_smoke_guards_preserved557():
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
