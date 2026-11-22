#!/usr/bin/env python3
"""Restore and execute a disposable copy of installed Chromium, no host OS writes.

An isolated browser copy is deliberately damaged and restored, then launched.
This is NOT an installed OS/library rollback or complete dynamic closure.
"""
from __future__ import annotations
import argparse
from hashlib import sha256
import os
from pathlib import Path
import shutil
import tempfile
from playwright.sync_api import sync_playwright

class ReplayBlocked(RuntimeError): pass

def digest(path):
    h = sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024*1024):
            h.update(chunk)
    return h.hexdigest()

def replay():
    data = Path(os.environ.get("TRACKER_DATA_DIR",""))
    if (not data.is_absolute() or not data.resolve().is_relative_to(Path("/tmp"))
            or not data.is_dir() or data.is_symlink() or data.stat().st_mode & 0o077
            or Path.cwd().resolve() == Path("/opt/tracker")):
        raise ReplayBlocked("Isolated private /tmp data required")
    with sync_playwright() as playwright:
        original = Path(playwright.chromium.executable_path)
        if (not original.is_absolute() or original.is_symlink()
                or not original.is_file() or original.stat().st_size < 1024*1024):
            raise ReplayBlocked("Trusted installed Chromium not available")
        with tempfile.TemporaryDirectory(dir=data, prefix="browser750-") as temp:
            root = Path(temp)
            copied = root / "chromium-copy"
            shutil.copytree(original.parent, copied, symlinks=True)
            for part in copied.rglob("*"):
                if part.is_symlink() and not part.resolve().is_relative_to(copied):
                    raise ReplayBlocked("External symlink in browser copy")
            executable = copied / original.name
            baseline = digest(original)
            if executable.is_symlink() or digest(executable) != baseline:
                raise ReplayBlocked("Copied executable differs")
            backup = root / "private-backup"
            shutil.copy2(executable, backup)
            with executable.open("r+b") as f:
                one = f.read(1)
                f.seek(0)
                f.write(bytes([one[0] ^ 255]))
                f.flush()
                os.fsync(f.fileno())
            if digest(executable) == baseline:
                raise ReplayBlocked("Disposable tamper not detected")
            shutil.copy2(backup, executable)
            if digest(executable) != baseline or digest(original) != baseline:
                raise ReplayBlocked("Restoration hash mismatch")
            browser = playwright.chromium.launch(
                headless=True, executable_path=str(executable), args=["--no-sandbox"])
            try:
                page = browser.new_page()
                page.route("**/*", lambda route: route.abort())
                page.set_content("<h1>Private replay 750</h1>")
                if page.locator("h1").inner_text() != "Private replay 750":
                    raise ReplayBlocked("Restored renderer failed")
                page.close()
            finally:
                browser.close()
            if digest(original) != baseline:
                raise ReplayBlocked("Original browser changed")
    print("RELEASE_750_OFFLINE_CHROMIUM_COPY_RESTORE=PASSED")
    print("RELEASE_750_INSTALLED_OS_ROLLBACK=NOT_TESTED")

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--disposable-replay", action="store_true", required=True)
    p.parse_args()
    try:
        replay()
    except (OSError,ValueError,ReplayBlocked) as exc:
        print("RELEASE_750_BROWSER_REPLAY=BLOCKED_"+type(exc).__name__)
        return 1
    return 0

if __name__=="__main__":
    raise SystemExit(main())
