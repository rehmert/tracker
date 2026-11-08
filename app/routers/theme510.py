"""Server-managed CSS for desktop browsers and installed Android PWA.

This route reads only one trusted file outside the deployable Git worktree.
It is read-only, scoped to the existing global app authentication dependency,
and deliberately sends no-store headers so theme edits need no redeploy.
"""
import os
import stat
from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import Response

from .. import config

router = APIRouter()
THEME_FILE = config.DATA_DIR / "tracker-theme.css"
DEFAULT_FILE = config.BASE_DIR / "static" / "css" / "tracker-server-theme-default510.css"
MAX_THEME_BYTES = 64 * 1024


def theme_bytes() -> tuple[bytes, str]:
    """Read a bounded regular CSS file without following symlinks.

    Missing, malformed, or unreadable overrides fall back to the known-good
    default. Never load a URL or accept a client-supplied filesystem path.
    """
    try:
        flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
        flags |= getattr(os, "O_NONBLOCK", 0)
        fd = os.open(THEME_FILE, flags)
        with os.fdopen(fd, "rb") as handle:
            info = os.fstat(handle.fileno())
            if not stat.S_ISREG(info.st_mode) or info.st_size > MAX_THEME_BYTES:
                raise ValueError("Theme must be a small regular file")
            data = handle.read(MAX_THEME_BYTES + 1)
        if len(data) > MAX_THEME_BYTES:
            raise ValueError("Theme exceeds size limit")
        data.decode("utf-8", errors="strict")
        return data, "override"
    except (OSError, ValueError, UnicodeDecodeError):
        return DEFAULT_FILE.read_bytes(), "default"


@router.get("/ui/theme.css", include_in_schema=False)
def theme_stylesheet():
    css, source = theme_bytes()
    return Response(
        content=css,
        media_type="text/css",
        headers={
            "Cache-Control": "private, no-store",
            "X-Content-Type-Options": "nosniff",
            "X-Tracker-Theme-Source": source,
            "Vary": "Cookie, Authorization",
        },
    )
