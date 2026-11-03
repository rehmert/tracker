"""Conservative browser-origin checks for write requests.

No cookies, sessions, tokens, or persistent state.
A missing Origin and missing Fetch Metadata remain compatible
with existing non-browser clients. This is defense in depth,
not a complete CSRF token system.
"""

from urllib.parse import urlsplit

UNSAFE_METHODS = frozenset({
    "POST", "PUT", "PATCH", "DELETE",
})


def _authority(value):
    """Parse a single HTTP(S) origin, without trusting userinfo."""
    if not value:
        return None

    if value != value.strip():
        return None

    try:
        parsed = urlsplit(value)

        if parsed.scheme.lower() not in ("http", "https"):
            return None

        if (
            not parsed.hostname
            or parsed.username is not None
            or parsed.password is not None
            or parsed.path
            or parsed.query
            or parsed.fragment
        ):
            return None

        # Accessing .port also rejects malformed port values.
        port = parsed.port
        if port is None:
            port = 443 if parsed.scheme.lower() == "https" else 80

        return parsed.hostname.lower(), port
    except ValueError:
        return None


def same_origin_host(origin, host):
    """Compare browser Origin to incoming Host.

    The request scheme may differ behind a TLS-terminating proxy.
    Compare hostname and explicit/default port, not request.url.scheme.
    """
    parsed = _authority(origin)
    if parsed is None:
        return False

    if not host or host != host.strip():
        return False

    try:
        # Host has no scheme. Match its explicit port to the
        # origin, or use the Origin scheme's default port.
        host_url = urlsplit("http://" + host)
        if (
            not host_url.hostname
            or host_url.username is not None
            or host_url.password is not None
            or host_url.path
            or host_url.query
            or host_url.fragment
        ):
            return False

        origin_scheme = urlsplit(origin).scheme.lower()
        default_port = 443 if origin_scheme == "https" else 80
        host_port = host_url.port

        if host_port is None:
            host_port = default_port

        return (
            host_url.hostname.lower() == parsed[0]
            and host_port == parsed[1]
        )
    except ValueError:
        return False


def reject_cross_origin_write(method, headers):
    """Return True only for demonstrably foreign browser writes."""
    if method.upper() not in UNSAFE_METHODS:
        return False

    fetch_site = headers.get("sec-fetch-site", "").strip().lower()

    if fetch_site == "cross-site":
        return True

    # A present Origin must be valid and match the target host.
    if "origin" in headers:
        return not same_origin_host(
            headers.get("origin", ""),
            headers.get("host", ""),
        )

    return False
