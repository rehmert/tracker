"""Release 546: validate exact top-level health JSON semantics."""

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/tracker-runtime-smoke.py"


@pytest.fixture
def smoke():
    spec = importlib.util.spec_from_file_location(
        "tracker_smoke546", SCRIPT
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize(
    "body",
    [
        b'{"ok":true}',
        b'{"ok": true}',
        b'{"ok":true,"instance":"DEV"}',
        b'{\n  "ok" : true,\n "ready": true\n}',
    ],
)
def test_valid_health_accepted546(smoke, body):
    smoke.validate_health_response(body)


@pytest.mark.parametrize(
    "body",
    [
        b'{"ok":false}',
        b'{"ok":null}',
        b'{"ok":1}',
        b'{"ok":"true"}',
        b'{"not_ok":true}',
        b'{"prefix_ok":true}',
        b'{"nested":{"ok":true}}',
        b'{"message":"\\"ok\\":true"}',
        b'{}',
        b'[]',
        b'true',
        b'null',
    ],
)
def test_invalid_health_status_rejected546(smoke, body):
    with pytest.raises(
        smoke.SmokeRequestError,
        match="invalid health status",
    ):
        smoke.validate_health_response(body)


@pytest.mark.parametrize(
    "body",
    [
        b'',
        b'not-json',
        b'{"ok":true',
        b'{"ok":true} trailing',
        b'\xff\xfe',
        b'{"ok": NaN,',
    ],
)
def test_malformed_health_json_rejected546(smoke, body):
    with pytest.raises(
        smoke.SmokeRequestError,
        match="invalid health JSON",
    ):
        smoke.validate_health_response(body)


def test_misleading_substring_cannot_pass546(smoke):
    with pytest.raises(smoke.SmokeRequestError):
        smoke.validate_health_response(
            b'{"not_ok":true}'
        )


def test_readiness_calls_validator546():
    source = SCRIPT.read_text()

    assert "validate_health_response(health)" in source
    assert (
        'b\'"ok":true\' not in health.replace'
        not in source
    )


def test_previous_guards_preserved546():
    source = SCRIPT.read_text()

    for marker in (
        "AUTH_REDIRECT HTTP",
        "AUTH_REJECTED HTTP",
        "auth.revoke(token)",
        "SIDEBAR_FAILURES=",
        "validate_sidebar_coverage(paths)",
        '"TRANSPORT " + category',
    ):
        assert marker in source
