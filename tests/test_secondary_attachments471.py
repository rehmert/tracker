"""Release 471 private attachment authorization tests."""

from pathlib import Path

import pytest
from fastapi import HTTPException

from app.secondary_attachments471 import (
    _checked_record471,
    STORED_NAME471,
    TABLES471,
    MIME471,
)


def test_attachments471_fixed_allowlists():
    assert TABLES471 == {
        "coa": "coas",
        "labs": "lab_reports",
    }
    assert set(MIME471) == {
        "application/pdf",
        "image/png",
        "image/jpeg",
        "image/webp",
    }

    for invalid in (
        "../private.pdf",
        "/etc/passwd",
        "..",
        ".",
        "a/b.pdf",
        "a\\b.pdf",
        "",
        "a" * 81,
    ):
        assert not STORED_NAME471.fullmatch(invalid)


def test_attachments471_rejects_unsupported_categories():
    for kind, rid in (
        ("admin", 1),
        ("backup", 1),
        ("../../coa", 1),
        ("coa", 0),
        ("labs", -1),
        ("labs", 2147483648),
        ("coa", True),
    ):
        with pytest.raises(HTTPException):
            _checked_record471(
                None, kind, rid
            )


def test_attachments471_no_write_capabilities():
    source = Path(
        "app/secondary_attachments471.py"
    ).read_text()

    assert "private_orm468(request)" in source
    assert "os.O_NOFOLLOW" in source
    assert "hashlib.sha256(" in source
    assert "MAX_BYTES471 + 1" in source

    for forbidden in (
        "open_upload",
        "INSERT INTO",
        "UPDATE users",
        "DELETE FROM",
        "subprocess.run(",
        "create_engine(",
        "request.path_params.get",
        "request.query_params.get",
        "FileResponse(",
        ".write_bytes(",
        ".write_text(",
    ):
        assert forbidden not in source, forbidden


def test_attachments471_get_only():
    from app.secondary_preview430 import preview_app

    matches = [
        route
        for route in preview_app.routes
        if getattr(route, "path", "") ==
        "/attachments/{kind}/{record_id}"
    ]

    assert len(matches) == 1
    assert matches[0].methods == {"GET"}


def test_attachments471_requires_kernel_nofollow():
    """Do not silently disable Linux symlink protections."""
    import os

    from pathlib import Path

    assert hasattr(os, "O_NOFOLLOW")
    assert hasattr(os, "O_DIRECTORY")

    source = Path(
        "app/secondary_attachments471.py"
    ).read_text()

    assert source.count("os.O_NOFOLLOW") == 2
    assert source.count("os.O_DIRECTORY") == 1

    assert 'getattr(os, "O_NOFOLLOW", 0)' not in source
    assert 'getattr(os, "O_DIRECTORY", 0)' not in source

    assert "stat.S_ISREG(info.st_mode)" in source
    assert "hashlib.sha256(" in source
