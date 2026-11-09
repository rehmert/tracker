"""Release 522: signed same-origin writes behind host-rewriting TLS proxies.

Proxy deployments can legitimately forward a public browser Origin while
rewriting Host to an internal authority. The legacy Origin-to-Host check then
mistakes native same-origin forms for cross-origin writes.

This narrowly conditioned exception is *not* a blanket Origin-guard bypass:
it needs a valid signed CSRF cookie + submission, browser-supplied
Sec-Fetch-Site: same-origin, and an HTTP(S) Origin (or the literal opaque
Origin "null"). It refuses unverifiable metadata, invalid/missing tokens,
malformed origins, duplicates and any same-site/cross-site request.

Signed proof is enforced here even when TRACKER_CSRF_ENFORCE=0 globally.
Unauthenticated/non-browser clients cannot use this proxy exception.
"""

from .csrf_runtime import HEADER_NAME
from .request_origin import UNSAFE_METHODS, _authority


def _single_header522(headers, name):
    """Accept zero or one header value; never interpret duplicated Origin."""
    if hasattr(headers, "getlist"):
        values = headers.getlist(name)
        if len(values) > 1:
            return False
    return True


def allow_signed_proxy_write522(method, headers, csrf_status):
    """Whether to override ONLY an Origin/Host mismatch already rejected.

    The caller must invoke this only after the existing origin guard rejects
    an unsafe browser write. No destination/remote-host allowlist is inferred
    from X-Forwarded-* headers, which untrusted peers could supply.
    """
    if method.upper() not in UNSAFE_METHODS:
        return False

    if csrf_status != "valid":
        return False

    if headers.get("sec-fetch-site", "").strip().lower() != "same-origin":
        return False

    if not _single_header522(headers, "origin"):
        return False

    if not _single_header522(headers, HEADER_NAME):
        return False

    origin = headers.get("origin")
    if not isinstance(origin, str):
        return False

    if origin == "null":
        return True

    # urlsplit alone accepts hostnames containing embedded whitespace.
    # Never relax the Origin guard for malformed/ambiguous authorities.
    if any(char.isspace() or ord(char) < 0x20 for char in origin):
        return False

    return _authority(origin) is not None
