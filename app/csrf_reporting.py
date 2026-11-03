"""Categorical CSRF reporting without enforcement.

Does not read request bodies, log credentials, or reject
requests. Form submissions without a header remain
uninspected in this release.
"""

from .csrf_runtime import (
    COOKIE_NAME,
    HEADER_NAME,
    load_key,
)
from .csrf_tokens import verify_pair

UNSAFE_METHODS = frozenset({
    "POST", "PUT", "PATCH", "DELETE",
})

REPORT_HEADER = "X-Tracker-CSRF-Report"

FORM_TYPES = frozenset({
    "application/x-www-form-urlencoded",
    "multipart/form-data",
})


def report_status(request):
    """Categorize write requests using headers and cookies only."""
    if request.method.upper() not in UNSAFE_METHODS:
        return None

    content_type = request.headers.get(
        "content-type", ""
    ).split(";", 1)[0].strip().lower()

    submitted = request.headers.get(HEADER_NAME)
    cookie = request.cookies.get(COOKIE_NAME)

    if not submitted:
        if content_type in FORM_TYPES:
            return "form-uninspected"
        return "missing"

    if not cookie:
        return "missing"

    try:
        key = load_key()
        return (
            "valid"
            if verify_pair(cookie, submitted, key)
            else "invalid"
        )
    except (OSError, ValueError):
        return "unavailable"
