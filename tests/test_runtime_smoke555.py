"""Release 555: reject unsafe local sidebar URLs."""

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/tracker-runtime-smoke.py"


@pytest.fixture
def smoke():
    spec = importlib.util.spec_from_file_location(
        "tracker_smoke555", SCRIPT
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def parse(smoke, html):
    parser = smoke.Links()
    parser.feed(html)
    parser.close()
    return parser


@pytest.mark.parametrize(
    "url",
    [
        "/vials",
        "/labs/history",
        "/reports/2026",
        "/items%20archived",
        "/vials?sort=name#top",
        "/vials#inventory",
        "/caf%C3%A9",
    ],
)
def test_valid_sidebar_urls555(smoke, url):
    parser = parse(
        smoke,
        f'<nav id="app-sidebar">'
        f'<a href="{url}">Link</a>'
        f'</nav>',
    )

    smoke.validate_sidebar_structure(parser)

    assert len(parser.paths) == 1
    assert parser.paths[0].startswith("/")


@pytest.mark.parametrize(
    "url",
    [
        "/vials%",
        "/vials%Q0",
        "/vials%0",
        "/vials%GG",
        "/vials%2",
    ],
)
def test_malformed_percent_encoding555(smoke, url):
    with pytest.raises(
        ValueError,
        match="malformed percent encoding",
    ):
        parse(
            smoke,
            '<nav id="app-sidebar">'
            f'<a href="{url}">Link</a>'
            '</nav>',
        )


@pytest.mark.parametrize(
    "url",
    [
        "/vials%00",
        "/vials%0A",
        "/vials%0d",
        "/vials%1f",
        "/vials%7F",
        "/vials%0a",
    ],
)
def test_encoded_control_bytes555(smoke, url):
    with pytest.raises(
        ValueError,
        match="encoded control characters",
    ):
        parse(
            smoke,
            '<nav id="app-sidebar">'
            f'<a href="{url}">Link</a>'
            '</nav>',
        )


@pytest.mark.parametrize(
    "url",
    [
        "/vials\ninjected",
        "/vials\rheaders",
        "/vials\tpath",
        "/vials\x00binary",
        "/vials\x7fdel",
    ],
)
def test_literal_control_characters555(smoke, url):
    with pytest.raises(
        ValueError,
        match="control characters",
    ):
        parse(
            smoke,
            '<nav id="app-sidebar">'
            f'<a href="{url}">Link</a>'
            '</nav>',
        )


def test_query_fragment_normalization_preserved555(smoke):
    parser = parse(
        smoke,
        '<nav id="app-sidebar">'
        '<a href="/vials">A</a>'
        '<a href="/vials?sort=name">B</a>'
        '<a href="/vials#section">C</a>'
        '<a href="/labs">D</a>'
        '</nav>',
    )

    smoke.validate_sidebar_structure(parser)

    assert parser.paths == [
        "/vials",
        "/vials",
        "/vials",
        "/labs",
    ]


def test_duplicate_sidebar_rejection_preserved555(smoke):
    parser = parse(
        smoke,
        '<nav id="app-sidebar"></nav>'
        '<nav id="app-sidebar"></nav>',
    )

    with pytest.raises(ValueError, match="found 2"):
        smoke.validate_sidebar_structure(parser)


def test_duplicate_attributes_rejected555(smoke):
    with pytest.raises(
        ValueError,
        match="Ambiguous sidebar link href attributes",
    ):
        parse(
            smoke,
            '<nav id="app-sidebar">'
            '<a href="/vials" href="/labs">Link</a>'
            '</nav>',
        )


def test_coverage_threshold_preserved555(smoke):
    parser = parse(
        smoke,
        '<nav id="app-sidebar">'
        + "".join(
            f'<a href="/page-{i}">Page</a>'
            for i in range(51)
        )
        + '</nav>',
    )

    smoke.validate_sidebar_structure(parser)

    with pytest.raises(ValueError, match="51/52"):
        smoke.validate_sidebar_coverage(parser.paths)


def test_previous_protections_preserved555():
    source = SCRIPT.read_text()

    for marker in (
        "validate_health_response(health)",
        "validate_dashboard_identity(dashboard, instance)",
        "validate_sidebar_structure(parser)",
        "validate_sidebar_coverage(paths)",
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
