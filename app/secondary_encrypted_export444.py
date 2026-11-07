"""Release 444: DEV-only encrypted secondary backup export/rehearsal.

Encryption uses the externally installed age CLI (X25519 age1 recipient).
The private identity is NEVER used for exporting and is never stored here.
Export inputs must be locally verified Release 442 ZIP archives.
Rehearsal decrypts ONLY into a 0700 temporary directory and performs the
same independent, non-destructive restore verification as Release 442.

This module never transfers files off-host and never restores live data.
"""

import hashlib
import os
import re
import shutil
import stat
import subprocess
import tempfile
from pathlib import Path

from .secondary_backup442 import MAX_RESTORE_BYTES, _no_links, verify_secondary_backup442
from .secondary_backup_ops443 import (
    _dev443, _exclusive_runner443, archives443, backup_directory443,
)

EXPORT_DIR = Path("/var/backups/tracker-secondary-export-dev")
RECIPIENT_RE = re.compile(r"age1[023456789acdefghjklmnpqrstuvwxyz]{58}\Z")
ENCRYPTED_RE = re.compile(
    r"tracker-secondary-\d{8}T\d{12}Z-[a-f0-9]{8}\.zip\.age\Z"
)
MAX_ENCRYPTED = MAX_RESTORE_BYTES + 16 * 1024 * 1024


def _age_binary444():
    """Do not resolve age through a privileged service's inherited PATH."""
    for raw in ("/usr/bin/age", "/usr/local/bin/age"):
        path = Path(raw)
        if path.is_file() and not path.is_symlink():
            st = path.stat()
            if (st.st_uid == 0
                and stat.S_ISREG(st.st_mode)
                and not stat.S_IMODE(st.st_mode) & 0o022
                and os.access(path, os.X_OK)):
                return str(path)
    raise FileNotFoundError(
        "Trusted age CLI missing; install the OS age package first"
    )


def _private_file444(path, *, expected_suffix=None):
    path = _no_links(Path(path).absolute())
    if (not path.is_file() or path.is_symlink()
        or path.stat().st_uid != os.geteuid()
        or stat.S_IMODE(path.stat().st_mode) != 0o600):
        raise ValueError("Recovery file must be owner-only (0600), regular and trusted")
    if expected_suffix and not path.name.endswith(expected_suffix):
        raise ValueError("Wrong recovery file type")
    return path


def _digest444(path):
    h = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def _run_age444(args):
    result = subprocess.run(
        [_age_binary444(), *args],
        stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, check=False, timeout=1800,
    )
    if result.returncode:
        # Deliberately do not print age stderr or identity paths in logs.
        raise RuntimeError("age encryption or decryption failed")
    return result


def _safe_export_dir444(destination=None, *, create=False):
    directory = backup_directory443(
        EXPORT_DIR if destination is None else destination, create=create,
    )
    return directory


def export_encrypted444(archive=None, *, recipient, backup_dir=None,
                        export_dir=None):
    """Encrypt a fully restored-and-verified private archive for one recipient.

    The original ZIP is not modified or deleted. The returned .age file is
    private and may be transferred by the operator using an approved method.
    No decryption key is needed or opened by this operation.
    """
    _dev443()
    if type(recipient) is not str or RECIPIENT_RE.fullmatch(recipient) is None:
        raise ValueError("Expected one standard age1 X25519 recipient")
    source_dir = backup_directory443(backup_dir)
    dest = _safe_export_dir444(export_dir, create=True)
    if dest == source_dir:
        raise ValueError("Encrypted exports require a separate directory")

    with _exclusive_runner443(source_dir):
        sources = archives443(source_dir)
        if not sources:
            raise ValueError("No secondary backup available to encrypt")
        if archive is None:
            source = sources[0]
        else:
            source = _private_file444(archive, expected_suffix=".zip")
            if source not in sources:
                raise ValueError("Archive is not a verified-managed secondary backup")
        original_digest = _digest444(source)
        report = verify_secondary_backup442(source)
        final = dest / (source.name + ".age")
        # Never overwrite an existing export.
        if final.exists() or final.is_symlink():
            raise FileExistsError("Encrypted export already exists")

        with tempfile.TemporaryDirectory(prefix=".secondary-age444-", dir=dest) as work:
            encrypted = Path(work) / "encrypted.age"
            _run_age444(["-r", recipient, "-o", str(encrypted), str(source)])
            os.chmod(encrypted, 0o600)
            encrypted = _private_file444(encrypted, expected_suffix=".age")
            if not 1 <= encrypted.stat().st_size <= MAX_ENCRYPTED:
                raise ValueError("Encrypted backup size is invalid")
            if _digest444(source) != original_digest:
                raise RuntimeError("Source backup changed during encryption")

            # No replacement / partial published output on failure.
            os.link(encrypted, final, follow_symlinks=False)
            os.chmod(final, 0o600)
            with final.open("rb") as check:
                os.fsync(check.fileno())
            directory_fd = os.open(str(dest), os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)

        return {
            "encrypted_file": str(final),
            "encrypted_sha256": _digest444(final),
            "encrypted_bytes": final.stat().st_size,
            "source_archive": source.name,
            "user_count": report["user_count"],
            "decrypt_rehearsed": False,
        }


def rehearse_encrypted444(encrypted, *, identity, expected_sha256=None):
    """Only decrypt to temporary storage and verify; NEVER restore live data."""
    _dev443()
    encrypted = _private_file444(encrypted, expected_suffix=".zip.age")
    if ENCRYPTED_RE.fullmatch(encrypted.name) is None:
        raise ValueError("Not a managed encrypted secondary archive")
    identity = _private_file444(identity)
    if not 1 <= encrypted.stat().st_size <= MAX_ENCRYPTED:
        raise ValueError("Encrypted archive exceeds bounded size")
    if (expected_sha256 is not None and
        (type(expected_sha256) is not str
         or not re.fullmatch(r"[0-9a-f]{64}", expected_sha256))):
        raise ValueError("Invalid expected encrypted checksum")
    before = _digest444(encrypted)
    if expected_sha256 is not None and before != expected_sha256:
        raise ValueError("Encrypted archive checksum mismatch")

    with tempfile.TemporaryDirectory(prefix="tracker-secondary-age-rehearsal444-") as tmp:
        # TemporaryDirectory uses 0700; plaintext never enters the export dir.
        plaintext = Path(tmp) / "recovered.zip"
        _run_age444([
            "-d", "-i", str(identity), "-o", str(plaintext), str(encrypted),
        ])
        os.chmod(plaintext, 0o600)
        plaintext = _private_file444(plaintext, expected_suffix=".zip")
        if plaintext.stat().st_size > MAX_ENCRYPTED:
            raise ValueError("Decrypted archive too large")
        verified = verify_secondary_backup442(plaintext)

    if _digest444(encrypted) != before:
        raise RuntimeError("Encrypted archive changed during rehearsal")
    return {
        "verified": True,
        "user_count": verified["user_count"],
        "files": verified["files"],
        "encrypted_sha256": before,
        "globally_atomic": False,
        "live_data_modified": False,
    }
