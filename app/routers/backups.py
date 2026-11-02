"""Backup creation, archive integrity and explicit isolated restore actions."""
import sqlite3
import subprocess
import zipfile
from urllib.parse import quote

from fastapi import APIRouter, Form, Request
from fastapi.responses import RedirectResponse

from .. import backup
from ..backup import create_backup, list_backups, prune_backups, verify_named_backup
from ..recovery_status import restore_status, invalidate_restore_evidence
from ..storage_health import backup_storage_status
from ..templating import render
from scripts.tracker_backup import verify_restorable

router = APIRouter()

ARCHIVE_ERRORS = (OSError, ValueError, KeyError, TypeError,
                  zipfile.BadZipFile, sqlite3.DatabaseError)
RESTORE_ERRORS = ARCHIVE_ERRORS + (
    subprocess.CalledProcessError, subprocess.TimeoutExpired,
)


def _message(text: str, error: bool = False):
    parameter = "err" if error else "msg"
    return RedirectResponse(
        "/backups?" + parameter + "=" + quote(text), status_code=303
    )


@router.get("/backups")
def backup_page(request: Request, msg: str = "", err: str = ""):
    return render(
        request, "backups.html", backups=list_backups(),
        recovery=restore_status(), storage=backup_storage_status(),
        backup_directory=backup.BACKUP_DIR,
        msg=msg, err=err,
    )


@router.post("/backups/create")
def backup_create():
    """A manual backup gets exactly the same restore gate as the timer."""
    try:
        archive = create_backup()
    except ARCHIVE_ERRORS as exc:
        return _message(f"Backup creation failed: {exc}", error=True)
    try:
        verify_restorable(archive)
    except RESTORE_ERRORS:
        # The archive remains for diagnosis and no existing backups are pruned.
        return _message(
            "Backup archive created, but the isolated restore test failed. "
            "The new archive was retained and older backups were not pruned.",
            error=True,
        )
    try:
        prune_backups()
    except ARCHIVE_ERRORS:
        return _message(
            "Backup passed its isolated restore test, but backup retention "
            "cleanup failed. Review the archive directory.",
            error=True,
        )
    return _message("Backup created and isolated restoration verified")


@router.post("/backups/restore-check")
def backup_restore_check(name: str = Form(...)):
    """Explicit on-demand restore test of the newest configured archive.

    Only the most recent archive may update the single latest-restore receipt.
    An archive path is never accepted from the caller.
    """
    try:
        archives = list_backups()
        if not archives or name != archives[0]["name"]:
            raise ValueError("Select the latest configured archive")
        # Revoke any earlier green result before rechecking this archive.
        # A failed retest must not leave stale success evidence visible.
        invalidate_restore_evidence(name)
        # Existing verifier enforces the archive filename and rejects symlinks.
        verify_named_backup(name)
        archive = backup.BACKUP_DIR / name
    except ARCHIVE_ERRORS:
        return _message("Cannot test restoration: invalid or missing latest backup", error=True)
    try:
        verify_restorable(archive)
    except RESTORE_ERRORS:
        return _message(
            "Isolated restoration failed. No success receipt was recorded; "
            "the live database and uploaded files were not modified.",
            error=True,
        )
    return _message(f"Isolated restoration verified for {name}")


@router.post("/backups/verify")
def backup_verify(name: str = Form(...)):
    try:
        manifest = verify_named_backup(name)
        count = len(manifest["files"])
        return _message(
            f"Verified {name}: {count} files, checksums and SQLite integrity passed"
        )
    except ARCHIVE_ERRORS as exc:
        return _message(f"Verification failed for {name}: {exc}", error=True)
