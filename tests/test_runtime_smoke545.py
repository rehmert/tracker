"""Release 545: fail closed on incomplete sidebar coverage."""

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/tracker-runtime-smoke.py"


@pytest.fixture
def smoke():
    spec = importlib.util.spec_from_file_location(
        "tracker_smoke545", SCRIPT
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def paths(count):
    return [
        f"/section-{index}"
        for index in range(count)
    ]


@pytest.mark.parametrize("count", [0, 1, 35, 51])
def test_incomplete_sidebar_rejected545(
    smoke, count
):
    with pytest.raises(
        ValueError,
        match=(
            "Sidebar coverage below required minimum: "
            rf"{count}/52"
        ),
    ):
        smoke.validate_sidebar_coverage(
            paths(count)
        )


@pytest.mark.parametrize("count", [52, 53, 60])
def test_complete_sidebar_accepted545(
    smoke, count, capsys
):
    smoke.validate_sidebar_coverage(
        paths(count)
    )

    output = capsys.readouterr().out

    assert "SIDEBAR_COVERAGE=PASS" in output
    assert f"unique={count}" in output
    assert "minimum=52" in output


def test_duplicate_links_do_not_inflate_coverage545(
    smoke
):
    incomplete = paths(51)

    # Repetition cannot disguise a missing destination.
    duplicated = incomplete + [
        incomplete[0]
    ] * 20

    with pytest.raises(
        ValueError,
        match="51/52 unique destinations",
    ):
        smoke.validate_sidebar_coverage(
            duplicated
        )


def test_exactly_52_unique_with_duplicates545(
    smoke, capsys
):
    complete = paths(52)

    smoke.validate_sidebar_coverage(
        complete + complete[:10]
    )

    output = capsys.readouterr().out

    assert "unique=52" in output


def test_nested_navigation_still_collected545(
    smoke
):
    parser = smoke.Links()

    parser.feed("""
        <nav id="app-sidebar">
          <a href="/first">First</a>
          <nav>
            <a href="/second">Second</a>
          </nav>
          <a href="/third">Third</a>
        </nav>
        <a href="/outside">Outside</a>
    """)

    parser.close()

    assert parser.paths == [
        "/first",
        "/second",
        "/third",
    ]


def test_coverage_gate_runs_before_traversal545():
    source = SCRIPT.read_text()

    assert (
        source.index(
            "validate_sidebar_coverage(paths)"
        )
        <
        source.index(
            "failures = []"
        )
    )


def test_prior_security_guards_preserved545():
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
