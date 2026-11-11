"""Release 554: reject ambiguous sidebar HTML attributes."""

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/tracker-runtime-smoke.py"


@pytest.fixture
def smoke():
    spec = importlib.util.spec_from_file_location(
        "tracker_smoke554", SCRIPT
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def parse(smoke, html):
    parser = smoke.Links()
    parser.feed(html)
    parser.close()
    return parser


def test_normal_sidebar_passes554(smoke):
    parser = parse(
        smoke,
        '<nav id="app-sidebar">'
        '<a href="/vials?sort=name#top">Vials</a>'
        '<nav>'
        '<a href="/labs">Labs</a>'
        '</nav>'
        '</nav>',
    )

    smoke.validate_sidebar_structure(parser)

    assert parser.paths == ["/vials", "/labs"]
    assert parser.sidebar_containers == 1
    assert parser.sidebar_depth == 0


@pytest.mark.parametrize(
    "html",
    [
        '<nav id="app-sidebar" id="other">'
        '<a href="/vials">Vials</a></nav>',
        '<nav id="other" id="app-sidebar">'
        '<a href="/vials">Vials</a></nav>',
        '<nav id="app-sidebar" id="app-sidebar">'
        '<a href="/vials">Vials</a></nav>',
        '<nav id="app-sidebar">'
        '<nav id="other" id="another">'
        '</nav></nav>',
    ],
)
def test_duplicate_sidebar_id_rejected554(
    smoke, html
):
    with pytest.raises(
        ValueError,
        match="Ambiguous sidebar navigation id attributes",
    ):
        parse(smoke, html)


@pytest.mark.parametrize(
    "html",
    [
        '<nav id="app-sidebar">'
        '<a href="/vials" href="/labs">Link</a>'
        '</nav>',
        '<nav id="app-sidebar">'
        '<a href="/vials" href="/vials">Link</a>'
        '</nav>',
        '<nav id="app-sidebar">'
        '<nav><a href="/labs" href="/vials">'
        'Link</a></nav></nav>',
    ],
)
def test_duplicate_sidebar_href_rejected554(
    smoke, html
):
    with pytest.raises(
        ValueError,
        match="Ambiguous sidebar link href attributes",
    ):
        parse(smoke, html)


def test_unrelated_document_attributes_ignored554(smoke):
    parser = parse(
        smoke,
        '<nav id="other" id="another">'
        '<a href="/outside" href="/outside2">'
        'Outside</a>'
        '</nav>'
        '<nav id="app-sidebar">'
        '<a href="/inside">Inside</a>'
        '</nav>',
    )

    smoke.validate_sidebar_structure(parser)

    assert parser.paths == ["/inside"]


def test_nested_duplicate_sidebar_still_rejected554(smoke):
    parser = parse(
        smoke,
        '<nav id="app-sidebar">'
        '<nav id="app-sidebar">'
        '<a href="/vials">Vials</a>'
        '</nav></nav>',
    )

    with pytest.raises(
        ValueError,
        match="found 2",
    ):
        smoke.validate_sidebar_structure(parser)


def test_unclosed_sidebar_still_rejected554(smoke):
    parser = parse(
        smoke,
        '<nav id="app-sidebar">'
        '<a href="/vials">Vials</a>',
    )

    with pytest.raises(
        ValueError,
        match="not closed",
    ):
        smoke.validate_sidebar_structure(parser)


def test_coverage_requirement_preserved554(smoke):
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

    with pytest.raises(
        ValueError,
        match="51/52",
    ):
        smoke.validate_sidebar_coverage(parser.paths)


def test_prior_smoke_protections_preserved554():
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
