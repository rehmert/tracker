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


def _proxy_browser_metadata522(method, headers):
    """Independent browser proof prerequisite for any proxy exception."""
    if method.upper() not in UNSAFE_METHODS:
        return False

    if headers.get("sec-fetch-site", "").strip().lower() != "same-origin":
        return False

    # The proxy exception must not override the main origin guard's
    # rejection of ambiguous multi-valued browser metadata.
    for field in ("host", "origin", "sec-fetch-site", HEADER_NAME):
        if not _single_header522(headers, field):
            return False

    origin = headers.get("origin")
    if not isinstance(origin, str):
        return False

    if origin == "null":
        return True

    # urlsplit alone accepts hostnames with embedded whitespace.
    if any(char.isspace() or ord(char) < 0x20 for char in origin):
        return False

    return _authority(origin) is not None


def allow_signed_proxy_write522(method, headers, csrf_status):
    """Accept an otherwise rejected Origin only with signed CSRF proof."""
    return (
        csrf_status == "valid"
        and _proxy_browser_metadata522(method, headers)
    )


def defer_proxy_multipart522(method, headers, csrf_status, content_type):
    """Authorize route-level validation, NEVER an unverified write.

    Multipart native forms have an uninspected body in HTTP middleware.
    Defer to the existing File/Form route dependency, where the complete
    parsed signed field + cookie are checked before endpoint mutation.
    """
    return (
        csrf_status == "form-uninspected"
        and content_type.split(";", 1)[0].strip().lower()
        == "multipart/form-data"
        and _proxy_browser_metadata522(method, headers)
    )
