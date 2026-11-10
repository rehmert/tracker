"""Release 532: test-harness reliability guarantees."""

import os
import socket

import pytest


def test_remote_connect_is_blocked532():
    """No real external request should be attempted."""
    with socket.socket(
        socket.AF_INET, socket.SOCK_STREAM
    ) as sock:
        with pytest.raises(
            AssertionError,
            match="External socket connection refused",
        ):
            sock.connect(("198.51.100.41", 443))


def test_remote_connect_ex_is_blocked532():
    """Alternate socket connection API must also be guarded."""
    with socket.socket(
        socket.AF_INET, socket.SOCK_STREAM
    ) as sock:
        with pytest.raises(
            AssertionError,
            match="External socket connection refused",
        ):
            sock.connect_ex(("203.0.113.9", 443))


def test_loopback_connection_still_works532():
    """Disposable local HTTP servers must remain usable."""
    with socket.socket(
        socket.AF_INET, socket.SOCK_STREAM
    ) as server:
        server.bind(("127.0.0.1", 0))
        server.listen(1)

        with socket.socket(
            socket.AF_INET, socket.SOCK_STREAM
        ) as client:
            client.settimeout(3)
            client.connect(server.getsockname())

            accepted, _ = server.accept()
            accepted.close()


def test_unix_socket_is_unaffected532():
    """Local Unix sockets must remain functional."""
    if not hasattr(socket, "AF_UNIX"):
        pytest.skip("Unix sockets unavailable")

    left, right = socket.socketpair(socket.AF_UNIX)

    with left, right:
        left.sendall(b"x")
        assert right.recv(1) == b"x"


@pytest.fixture
def temporary_instance532(monkeypatch):
    """Normal pytest cleanup must run before the autouse guard."""
    monkeypatch.setenv("TRACKER_INSTANCE", "PROD")
    yield


def test_monkeypatch_restored_before_guard532(temporary_instance532):
    assert os.environ["TRACKER_INSTANCE"] == "PROD"
