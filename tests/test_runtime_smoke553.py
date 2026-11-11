"""Release 553: require a unique, complete sidebar container."""

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/tracker-runtime-smoke.py"


@pytest.fixture
def smoke():
    spec = importlib.util.spec_from_file_location(
        "tracker_smoke553", SCRIPT
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def parse(smoke, html):
    parser = smoke.Links()
    parser.feed(html)
    parser.close()
    return parser


def test_single_sidebar_passes553(smoke, capsys):
    parser = parse(
        smoke,
        '<nav id="app-sidebar">'
        '<a href="/vials?sort=name#top">Vials</a>'
        '<nav><a href="/labs">Labs</a></nav>'
        '</nav>',
    )

    smoke.validate_sidebar_structure(parser)

    assert parser.paths == ["/vials", "/labs"]
    assert parser.sidebar_containers == 1
    assert parser.sidebar_depth == 0
    assert (
        "SIDEBAR_STRUCTURE=PASS containers=1"
        in capsys.readouterr().out
    )


def test_missing_sidebar_rejected553(smoke):
    parser = parse(
        smoke,
        '<nav id="other"><a href="/vials">Vials</a></nav>',
    )

    with pytest.raises(
        ValueError, match="found 0"
    ):
        smoke.validate_sidebar_structure(parser)


def test_duplicate_sidebar_rejected553(smoke):
    parser = parse(
        smoke,
        '<nav id="app-sidebar">'
        '<a href="/vials">Vials</a></nav>'
        '<nav id="app-sidebar">'
        '<a href="/labs">Labs</a></nav>',
    )

    assert parser.paths == ["/vials", "/labs"]

    with pytest.raises(
        ValueError, match="found 2"
    ):
        smoke.validate_sidebar_structure(parser)


def test_nested_duplicate_id_rejected553(smoke):
    parser = parse(
        smoke,
        '<nav id="app-sidebar">'
        '<nav id="app-sidebar">'
        '<a href="/labs">Labs</a>'
        '</nav></nav>',
    )

    with pytest.raises(
        ValueError, match="found 2"
    ):
        smoke.validate_sidebar_structure(parser)


def test_unclosed_sidebar_rejected553(smoke):
    parser = parse(
        smoke,
        '<nav id="app-sidebar">'
        '<a href="/vials">Vials</a>',
    )

    with pytest.raises(
        ValueError, match="not closed"
    ):
        smoke.validate_sidebar_structure(parser)


def test_52_endpoints_still_required553(smoke):
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
        ValueError, match="51/52"
    ):
        smoke.validate_sidebar_coverage(parser.paths)


def test_previous_protections_preserved553():
    source = SCRIPT.read_text()

    for marker in (
        "validate_health_response(health)",
        "validate_dashboard_identity(dashboard, instance)",
        "validate_sidebar_coverage(paths)",
        "response.read(MAX_RESPONSE_BYTES + 1)",
        "if len(body) > MAX_RESPONSE_BYTES:",
        "Authenticated sidebar rejected: ",
        "auth.revoke(token)",
        "if match is None:",
        "if len(declarations) != 1",
        "urllib.parse.urlsplit(url)",
    ):
        assert marker in source, marker
