"""Release 500: narrowly scoped Labs POST origin exception.

The global Origin/Host guard can reject ordinary Labs HTML forms behind
reverse proxies or when browsers emit Origin: null. A rejected browser POST
can proceed only if all independent signals agree: exact Labs route,
same-origin Fetch Metadata, and verified signed CSRF cookie/submission.
All route-level authentication and workspace authorization remain active.
"""
import re

from .request_origin import _authority


_EXACT = frozenset({
    "/labs",
    "/labs/import-csv",
})

_DYNAMIC = (
    re.compile(r"/labs/[1-9][0-9]{0,9}/(?:results|import-csv|edit|delete)\Z"),
    re.compile(r"/lab-results/[1-9][0-9]{0,9}/(?:edit|delete)\Z"),
)


def is_lab_write500(path):
    return (
        isinstance(path, str)
        and (
            path in _EXACT
            or any(pattern.fullmatch(path) for pattern in _DYNAMIC)
        )
    )


def allow_lab_proxy_write500(method, path, headers, csrf_report):
    """Allow strictly verified Labs form writes rejected by Origin/Host check."""
    if (
        method.upper() != "POST"
        or not is_lab_write500(path)
        or csrf_report != "valid"
        or headers.get("sec-fetch-site", "").strip().lower() != "same-origin"
    ):
        return False

    origin = headers.get("origin", "")
    if not isinstance(origin, str):
        return False
    if origin == "null":
        return True
    if not origin.lower().startswith("https://"):
        return False
    return _authority(origin) is not None
