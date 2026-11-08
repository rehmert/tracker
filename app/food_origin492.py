"""Releases 492-493: tightly constrained proxy-origin exception for Food.

Some production browsers send Origin: null even on a same-origin Food form
submission. Never treat a null origin as trusted by itself. This exceptional
path requires the browser's same-origin Fetch Metadata, a valid signed CSRF
cookie/submission pair, an exact allowlisted Food POST, and either a
syntactically valid HTTPS Origin or the exact literal opaque Origin "null".
Other paths, methods, and cross-site/same-site writes remain blocked.
"""

import re

from .request_origin import _authority


_EXACT = frozenset({
    "/food/entry", "/food/water", "/food/targets",
    "/food/photo", "/food/template/save",
})

_DYNAMIC = (
    re.compile(r"/food/(?:quick|favorite)/[1-9][0-9]{0,9}\Z"),
    re.compile(r"/food/(?:water|entry)/[1-9][0-9]{0,9}/delete\Z"),
    re.compile(r"/food/entry/[1-9][0-9]{0,9}/(?:edit|nutrition)\Z"),
    re.compile(r"/food/template/[1-9][0-9]{0,9}/(?:log|rename|delete)\Z"),
)


def is_food_write492(path):
    return (
        isinstance(path, str)
        and (
            path in _EXACT
            or any(pattern.fullmatch(path) for pattern in _DYNAMIC)
        )
    )


def allow_food_proxy_write492(method, path, headers, csrf_report):
    """Verify the very limited Food proxy/opaque-origin exception.

    Called only after normal cross-origin verification rejected the write.
    Origin "null" never suffices without independent signed CSRF plus
    Sec-Fetch-Site: same-origin; missing or untrusted metadata fails shut.
    """

    if (
        method.upper() != "POST"
        or not is_food_write492(path)
        or csrf_report != "valid"
        or headers.get("sec-fetch-site", "").strip().lower() != "same-origin"
    ):
        return False

    origin = headers.get("origin", "")
    if not isinstance(origin, str):
        return False

    # Some legitimate Food form submissions have an opaque Origin:
    # literal "null". This is accepted ONLY after all four guards above
    # passed, notably independent signed CSRF and browser Fetch Metadata.
    if origin == "null":
        return True

    if not origin.lower().startswith("https://"):
        return False

    return _authority(origin) is not None
