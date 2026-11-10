"""Release 552: normalize sidebar URLs before coverage checks."""

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/tracker-runtime-smoke.py"


@pytest.fixture
def smoke():
    spec = importlib.util.spec_from_file_location(
        "tracker_smoke552", SCRIPT
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def extract(smoke, urls):
    parser = smoke.Links()

    links = "".join(
        f'<a href="{url}">Link</a>'
        for url in urls
    )

    parser.feed(
        '<nav id="app-sidebar">'
        + links
        + '</nav>'
    )

    return parser.paths


def test_query_and_fragment_normalization552(smoke):
    assert extract(
        smoke,
        [
            "/vials",
            "/vials?sort=name",
            "/vials#inventory",
            "/vials?sort=name#inventory",
        ],
    ) == [
        "/vials",
        "/vials",
        "/vials",
        "/vials",
    ]


def test_untrusted_links_excluded552(smoke):
    assert extract(
        smoke,
        [
            "https://example.com",
            "http://example.com/page",
            "//example.com/page",
            "javascript:alert(1)",
            "mailto:test@example.com",
            "#section",
            "?sort=asc",
            "relative/path",
            "/safe",
        ],
    ) == ["/safe"]


def test_nested_sidebar_navigation_preserved552(smoke):
    parser = smoke.Links()

    parser.feed(
        '<nav id="app-sidebar">'
        '<a href="/vials#top">Vials</a>'
        '<nav>'
        '<a href="/labs?view=recent">Labs</a>'
        '</nav>'
        '<a href="/reports">Reports</a>'
        '</nav>'
        '<a href="/outside">Outside</a>'
    )

    assert parser.paths == [
        "/vials",
        "/labs",
        "/reports",
    ]


def test_coverage_uses_unique_normalized_paths552(
    smoke, capsys
):
    urls = [
        f"/page-{i}" for i in range(51)
    ]

    urls.extend([
        "/page-0?sort=name",
        "/page-0#section",
    ])

    paths = extract(smoke, urls)

    assert len(paths) == 53
    assert len(set(paths)) == 51

    with pytest.raises(
        ValueError,
        match="51/52 unique destinations",
    ):
        smoke.validate_sidebar_coverage(paths)

    assert (
        "SIDEBAR_COVERAGE=PASS"
        not in capsys.readouterr().out
    )


def test_exact_coverage_succeeds552(smoke, capsys):
    urls = [
        f"/page-{i}" for i in range(52)
    ]

    paths = extract(smoke, urls)

    smoke.validate_sidebar_coverage(paths)

    assert (
        "SIDEBAR_COVERAGE=PASS unique=52 minimum=52"
        in capsys.readouterr().out
    )


def test_prior_smoke_protections_preserved552():
    source = SCRIPT.read_text()

    for marker in (
        "validate_health_response(health)",
        "validate_dashboard_identity(dashboard, instance)",
        "validate_sidebar_coverage(paths)",
        "response.read(MAX_RESPONSE_BYTES + 1)",
        "if len(body) > MAX_RESPONSE_BYTES:",
        "Authenticated sidebar rejected: ",
        "auth.revoke(token)",
        "SIDEBAR_FAILURES=",
    ):
        assert marker in source

    assert "if match is None:" in source
    assert "if len(declarations) != 1" in source
