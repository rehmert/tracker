"""Release 547: verify dashboard identity before sidebar traversal."""

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/tracker-runtime-smoke.py"


@pytest.fixture
def smoke():
    spec = importlib.util.spec_from_file_location(
        "tracker_smoke547", SCRIPT
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def page(instance):
    return (
        b"<html><head><title>Tracker</title></head>"
        + (
            f'<body class="tracker-instance--{instance}">'
        ).encode()
        + b"<nav id='app-sidebar'></nav></body></html>"
    )


@pytest.mark.parametrize(
    "instance",
    ["DEV", "PROD"],
)
def test_correct_dashboard_identity547(
    smoke, instance, capsys
):
    smoke.validate_dashboard_identity(
        page(instance.lower()), instance
    )

    output = capsys.readouterr().out

    assert (
        f"DASHBOARD_IDENTITY=PASS instance={instance}"
        in output
    )


@pytest.mark.parametrize(
    "instance,wrong",
    [
        ("DEV", "prod"),
        ("PROD", "dev"),
    ],
)
def test_cross_instance_rejected547(
    smoke, instance, wrong
):
    with pytest.raises(
        smoke.SmokeRequestError,
        match="missing dashboard title/instance badge",
    ):
        smoke.validate_dashboard_identity(
            page(wrong), instance
        )


def test_missing_badge_rejected547(smoke):
    with pytest.raises(smoke.SmokeRequestError):
        smoke.validate_dashboard_identity(
            b"<html><title>Tracker</title></html>",
            "DEV",
        )


def test_missing_title_rejected547(smoke):
    with pytest.raises(smoke.SmokeRequestError):
        smoke.validate_dashboard_identity(
            b'<body class="tracker-instance--dev"></body>',
            "DEV",
        )


@pytest.mark.parametrize(
    "instance",
    ["", "STAGING", "dev", "prod"],
)
def test_invalid_instance_rejected547(
    smoke, instance
):
    with pytest.raises(
        ValueError,
        match="Invalid smoke instance",
    ):
        smoke.validate_dashboard_identity(
            page("dev"), instance
        )


def test_identity_gate_precedes_sidebar_discovery547():
    source = SCRIPT.read_text()

    run_source = source[
        source.index("def run(instance, envfile):")
    :]

    assert (
        run_source.index(
            "validate_dashboard_identity(dashboard, instance)"
        )
        <
        run_source.index("parser = Links()")
    )


def test_previous_health_and_sidebar_guards547():
    source = SCRIPT.read_text()

    for marker in (
        "validate_health_response(health)",
        "validate_sidebar_coverage(paths)",
        "AUTH_REDIRECT HTTP",
        "AUTH_REJECTED HTTP",
        "auth.revoke(token)",
        "SIDEBAR_FAILURES=",
        '"TRANSPORT " + category',
    ):
        assert marker in source
