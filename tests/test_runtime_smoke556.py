"""Release 556: reject ambiguous sidebar path navigation."""

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/tracker-runtime-smoke.py"


@pytest.fixture
def smoke():
    spec = importlib.util.spec_from_file_location(
        "tracker_smoke556", SCRIPT
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
        ("/reports/2026", "/reports/2026"),
        ("/items%20archived", "/items%20archived"),
        ("/caf%C3%A9", "/caf%C3%A9"),
        ("/vials?sort=name#top", "/vials"),
        ("/vials#inventory", "/vials"),
        ("/reports/v1.2", "/reports/v1.2"),
        ("/vials/item..backup", "/vials/item..backup"),
    ],
)
def test_valid_urls_preserved556(smoke, url, expected):
    assert parse(smoke, url).paths == [expected]


@pytest.mark.parametrize(
    "url",
    [
        "/./vials",
        "/../vials",
        "/reports/../vials",
        "/reports/./vials",
        "/reports/%2e%2e/vials",
        "/reports/%2E%2E/vials",
        "/reports/.%2e/vials",
        "/reports/%2e./vials",
        "/reports/%2e/vials",
    ],
)
def test_dot_segments_rejected556(smoke, url):
    with pytest.raises(
        ValueError, match="dot path segments"
    ):
        parse(smoke, url)


@pytest.mark.parametrize(
    "url",
    [
        "/reports//vials",
        "/reports/%2f/vials",
        "/reports/%2F/vials",
        "/reports/%2f%2fvials",
    ],
)
def test_ambiguous_separators_rejected556(smoke, url):
    with pytest.raises(
        ValueError, match="ambiguous separators"
    ):
        parse(smoke, url)


@pytest.mark.parametrize(
    "url",
    [
        "/reports%5cvials",
        "/reports%5Cvials",
        "/reports\\vials",
    ],
)
def test_backslash_rejected556(smoke, url):
    with pytest.raises(
        ValueError, match="backslash separators"
    ):
        parse(smoke, url)


@pytest.mark.parametrize(
    "url,expected",
    [
        ("/vials%", "malformed percent encoding"),
        ("/vials%Q0", "malformed percent encoding"),
        ("/vials%00", "encoded control characters"),
        ("/vials%0A", "encoded control characters"),
        ("/vials%7F", "encoded control characters"),
    ],
)
def test_release555_safety_preserved556(
    smoke, url, expected
):
    with pytest.raises(ValueError, match=expected):
        parse(smoke, url)


def test_duplicate_attribute_rejection_preserved556(smoke):
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


def test_duplicate_sidebar_rejection_preserved556(smoke):
    parser = smoke.Links()
    parser.feed(
        '<nav id="app-sidebar"></nav>'
        '<nav id="app-sidebar"></nav>'
    )
    parser.close()

    with pytest.raises(ValueError, match="found 2"):
        smoke.validate_sidebar_structure(parser)


def test_coverage_threshold_preserved556(smoke):
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


def test_prior_smoke_guards_preserved556():
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
        "if match is None:",
        "if len(declarations) != 1",
        "urllib.parse.urlsplit(url)",
        "parser.close()",
    ):
        assert marker in source, marker
