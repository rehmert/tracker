"""Strict login-origin policy for a TLS-terminating reverse proxy.

Other application writes retain the existing origin guard.

A browser's Sec-Fetch-Site: same-origin attests that the request
was initiated by the same origin as the public-facing page.
A public HTTPS Origin can differ from the internal FastAPI Host
when the reverse proxy rewrites Host.

The independent signed, short-lived login CSRF token remains
mandatory. No generic authorization or bypass is introduced.
"""

from .request_origin import (
    _authority,
    reject_cross_origin_write,
)


def reject_login_origin(method, headers):
    """Reject suspicious login submissions, including foreign origins."""

    if method.upper() != "POST":
        return reject_cross_origin_write(method, headers)

    # Preserve the existing origin check whenever it succeeds.
    if not reject_cross_origin_write(method, headers):
        return False

    # Allow a proxy Host mismatch only when the browser itself
    # describes the request as same-origin.
    fetch_site = headers.get(
        "sec-fetch-site", ""
    ).strip().lower()

    if fetch_site != "same-origin":
        return True

    origin = headers.get("origin", "")

    # Origin must be a single, syntactically valid HTTPS origin.
    # Missing, null, malformed and HTTP origins do not qualify.
    if not origin.startswith("https://"):
        return True

    if _authority(origin) is None:
        return True

    return False


def reject_write_with_login_exception(method, path, headers):
    """Apply the existing guard except for narrowly verified login POSTs."""

    if path == "/login" and method.upper() == "POST":
        return reject_login_origin(method, headers)

    return reject_cross_origin_write(method, headers)
