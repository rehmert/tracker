"""Always isolate the test suite from the running Tracker database."""
import os
import tempfile
from pathlib import Path

# pytest imports conftest before importing test modules or app.db. Always use
# an independently generated directory, even when TRACKER_DATA_DIR is set.
_TEST_DIR = tempfile.TemporaryDirectory(prefix="tracker-pytest-isolated-")
TEST_DATA_DIR = Path(_TEST_DIR.name).resolve()
os.environ["TRACKER_DATA_DIR"] = str(TEST_DATA_DIR)
os.environ.pop("TRACKER_USER", None)
os.environ.pop("TRACKER_PASS", None)


def pytest_sessionstart(session):
    """Refuse to run if another import initialized the app against a different DB."""
    import sys
    cfg = sys.modules.get("app.config")
    if cfg is not None and Path(cfg.DATA_DIR).resolve() != TEST_DATA_DIR:
        raise RuntimeError("Refusing to test: Tracker database was initialized outside the isolated test directory")


def pytest_sessionfinish(session, exitstatus):
    # SQLAlchemy connections are usually released at process exit; keeping the
    # temp dir until process exit avoids Windows file-lock teardown errors.
    pass


# Release 532: protect test isolation from external network dependencies
# and leaked process-wide instance configuration.
import ipaddress
import socket

import pytest


@pytest.fixture(autouse=True)
def _tracker_reliability_isolation532():
    """Reject external Python socket connections during tests.

    Localhost remains available for disposable HTTP/HTTPS QA servers.
    This guard applies to in-process sockets while a test is running.
    Subprocesses and Chromium have separate isolation requirements.
    """
    names = ("TRACKER_DATA_DIR", "TRACKER_INSTANCE")
    before = {name: os.environ.get(name) for name in names}

    patches = pytest.MonkeyPatch()

    real_connect = socket.socket.connect
    real_connect_ex = socket.socket.connect_ex

    def verify_destination(sock, address):
        # Unix-domain sockets and other non-IP families are unaffected.
        if sock.family not in (socket.AF_INET, socket.AF_INET6):
            return

        if not isinstance(address, tuple) or not address:
            raise AssertionError(
                "Invalid network destination in Tracker test"
            )

        host = address[0]

        try:
            loopback = ipaddress.ip_address(
                str(host).split("%", 1)[0]
            ).is_loopback
        except ValueError:
            loopback = host == "localhost"

        if not loopback:
            raise AssertionError(
                "External socket connection refused "
                "by Tracker test isolation"
            )

    def guarded_connect(sock, address):
        verify_destination(sock, address)
        return real_connect(sock, address)

    def guarded_connect_ex(sock, address):
        verify_destination(sock, address)
        return real_connect_ex(sock, address)

    patches.setattr(
        socket.socket, "connect", guarded_connect
    )
    patches.setattr(
        socket.socket, "connect_ex", guarded_connect_ex
    )

    try:
        yield
    finally:
        patches.undo()

        # This autouse fixture has no dependency on the normal
        # monkeypatch fixture. Consequently its finalizer runs
        # after normal function-scoped monkeypatch cleanup.
        after = {
            name: os.environ.get(name) for name in names
        }

        assert after == before, (
            "Test leaked TRACKER_DATA_DIR/TRACKER_INSTANCE; "
            f"before={before!r}, after={after!r}"
        )
