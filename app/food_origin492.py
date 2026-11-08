"""Release 492: constrained HTTPS reverse-proxy origin exception for Food.

The existing origin guard compares the browser's public Origin with the
internal Host FastAPI may receive from a reverse proxy. This narrowly
permits signed, browser-attested same-origin Food writes when those
authorities differ. No proxy-supplied headers are trusted; arbitrary paths,
unsigned requests, same-site and cross-site requests remain blocked.
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
    """Require exact Food POST + signed CSRF + browser same-origin HTTPS.

    This function is considered only AFTER the existing cross-origin
    guard rejected the request. It never permits HTTP origins, missing
    or contradictory browser metadata, non-Food paths, or invalid tokens.
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

    if not origin.lower().startswith("https://"):
        return False

    return _authority(origin) is not None
