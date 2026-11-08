"""Release 517: request-local DNS pinning for user-selected public product URLs.

No external sockets are opened. Tests stub name resolution, sockets, TLS,
HTTP connections, and redirect responses.
"""
import socket
from urllib.parse import urlsplit

import pytest

from app import vendor_url_extract as vendor


def public_dns(monkeypatch, ip="8.8.8.8"):
    calls = []

    def lookup(host, port, **kwargs):
        calls.append((host, port))
        return [(socket.AF_INET, socket.SOCK_STREAM, 0, "",
                 (ip, port))]

    monkeypatch.setattr(vendor.socket, "getaddrinfo", lookup)
    return calls


def test_517_public_url_uses_only_public_dns(monkeypatch):
    calls = public_dns(monkeypatch)
    assert vendor.public_url("https://example.com/item") == "https://example.com/item"
    assert calls == [("example.com", 443)]

    public_dns(monkeypatch, "10.10.1.10")
    with pytest.raises(ValueError, match="Private"):
        vendor.public_url("https://example.com/item")


def test_517_rejects_mixed_public_and_private_dns(monkeypatch):
    monkeypatch.setattr(
        vendor.socket, "getaddrinfo",
        lambda *a, **k: [
            (socket.AF_INET, socket.SOCK_STREAM, 0, "", ("8.8.8.8", 443)),
            (socket.AF_INET, socket.SOCK_STREAM, 0, "", ("127.0.0.1", 443)),
        ],
    )
    with pytest.raises(ValueError, match="Private"):
        vendor.public_url("https://example.com/item")


@pytest.mark.parametrize("unsafe", [
    "file:///etc/passwd", "https://localhost/a", "https://127.0.0.1/a",
    "https://user:pass@example.com/", "http://169.254.169.254/latest",
    "https://example.com:9000/", "https://example.com/\r\nheader",
])
def test_517_rejects_unsafe_public_urls(unsafe):
    with pytest.raises(ValueError):
        vendor.public_url(unsafe)


def test_517_plain_http_connection_never_connects_to_untrusted_hostname(
    monkeypatch
):
    calls = []

    class Socket:
        def close(self):
            pass

    monkeypatch.setattr(
        vendor.socket, "create_connection",
        lambda address, timeout: (
            calls.append((address, timeout)) or Socket()
        ),
    )

    conn = vendor._PinnedHTTPConnection("example.com", 80, "8.8.8.8")
    conn.connect()
    assert calls == [(("8.8.8.8", 80), vendor.REQUEST_TIMEOUT)]
    conn.close()


def test_517_tls_uses_original_hostname_for_certificate_check(monkeypatch):
    calls = []

    class Socket:
        def close(self):
            calls.append("close")

    class SSL:
        def wrap_socket(self, sock, *, server_hostname):
            calls.append(("sni", server_hostname))
            return sock

    def connect(addr, timeout):
        calls.append(("ip", addr, timeout))
        return Socket()

    monkeypatch.setattr(vendor.socket, "create_connection", connect)
    conn = vendor._PinnedHTTPSConnection("example.com", 443, "8.8.8.8")
    conn._context = SSL()
    conn.connect()
    assert calls[0] == ("ip", ("8.8.8.8", 443), vendor.REQUEST_TIMEOUT)
    assert ("sni", "example.com") in calls
    conn.close()


def test_517_html_read_is_bounded_and_uses_pinned_destination(monkeypatch):
    calls = []

    class Response:
        status = 200
        headers = {"Content-Type": "text/html; charset=utf-8"}

        def getheader(self, key):
            return self.headers.get(key)

        def read(self, n):
            calls.append(("read_cap", n))
            return b"<html><title>Product</title></html>"

    class Connection:
        def __init__(self, hostname, port, ip):
            calls.append(("connect_target", hostname, port, ip))

        def request(self, method, target, headers):
            calls.append(("request", method, target, headers.get("Host")))

        def getresponse(self):
            return Response()

        def close(self):
            calls.append(("closed",))

    monkeypatch.setattr(vendor, "_PinnedHTTPSConnection", Connection)
    code, redirect, content = vendor._fetch_once(
        "https://example.com/item?a=b",
        urlsplit("https://example.com/item?a=b"),
        "8.8.8.8",
    )
    assert code == 200 and redirect is None
    assert "Product" in content
    assert ("connect_target", "example.com", 443, "8.8.8.8") in calls
    assert ("request", "GET", "/item?a=b", "example.com") in calls
    assert ("read_cap", vendor.MAX_HTML + 1) in calls
    assert ("closed",) in calls


def test_517_redirect_must_pass_fresh_public_dns_validation(monkeypatch):
    calls = []

    def lookup(host, port, **kwargs):
        calls.append(host)
        ip = "8.8.8.8" if host == "example.com" else "127.0.0.1"
        return [(socket.AF_INET, socket.SOCK_STREAM, 0, "", (ip, port))]

    monkeypatch.setattr(vendor.socket, "getaddrinfo", lookup)
    received = []
    monkeypatch.setattr(
        vendor, "_fetch_once",
        lambda url, parsed, ip: (
            received.append((url, ip)) or (302, "http://127.0.0.1/private", None)
        ),
    )
    with pytest.raises(ValueError, match="Private"):
        vendor.fetch_public_page("https://example.com/public")
    assert len(received) == 1
    assert received[0][1] == "8.8.8.8"
    assert calls == ["example.com", "127.0.0.1"]


def test_517_redirect_depth_remains_limited(monkeypatch):
    public_dns(monkeypatch)
    monkeypatch.setattr(
        vendor, "_fetch_once",
        lambda *a: (302, "/next", None),
    )
    with pytest.raises(ValueError, match="Too many redirects"):
        vendor.fetch_public_page("https://example.com/item")
