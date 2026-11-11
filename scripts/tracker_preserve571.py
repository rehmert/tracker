#!/usr/bin/env python3
"""Preserve a successful, retained Release 570 replay without touching Tracker.

Dry-run by default. --execute stores exact wheel files, browser binaries,
a file-hash manifest, observed package baseline and host compatibility facts.
Only root on tracker-dev may run this installed script.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shutil
import socket
import stat
import subprocess
import sys
import tempfile

from packaging.utils import canonicalize_name, parse_wheel_filename

APP = Path("/opt/tracker")
SCRIPT = APP / "scripts/tracker_preserve571.py"
ARCHIVES = Path("/var/lib/tracker-reproducibility")
BASELINE = APP / "docs/dependencies/observed-2026-11-11-py313.json"
CONSTRAINTS = APP / "docs/dependencies/candidate-constraints-py313.txt"
REPLAY_NAME = re.compile(r"tracker-freshenv570-[a-zA-Z0-9]+\Z")
HASH = re.compile(r"[0-9a-f]{64}\Z")
MARKERS = (
    "REPLAY_PREFLIGHT=PASSED",
    "FRESHENV_PACKAGE_BASELINE=PASSED",
    "FRESHENV_CHROMIUM_LAUNCH=PASSED",
    "FRESHENV_BACKEND_SUITE=PASSED",
    "FRESHENV_BROWSER_SUITE=PASSED",
    "ISOLATED_STRICT_CSRF_BROWSER=PASSED",
    "WHEELHOUSE_WHEELS=44",
)


class ArchiveError(RuntimeError):
    pass


def ensure(ok: bool, reason: str) -> None:
    if not ok:
        raise ArchiveError(reason)


def sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def owner_checked(path: Path, *, directory: bool, private: bool) -> None:
    st = path.lstat()
    test = stat.S_ISDIR if directory else stat.S_ISREG
    ensure(test(st.st_mode) and st.st_uid == 0,
           "Expected a root-owned ordinary directory or file")
    if private:
        ensure(not (stat.S_IMODE(st.st_mode) & 0o077),
               "Expected root-only permissions")


def git(*args: str) -> str:
    return subprocess.check_output(
        ["git", "-c", f"safe.directory={APP}", "-C", str(APP), *args],
        text=True,
    ).strip()


def preflight() -> str:
    ensure(os.geteuid() == 0
           and socket.gethostname().split(".", 1)[0] == "tracker-dev",
           "Run as root on tracker-dev")
    ensure(Path(__file__).resolve() == SCRIPT,
           "Run installed DEV script")
    ensure(git("branch", "--show-current") == "main"
           and not git("status", "--porcelain"),
           "Installed DEV checkout must be clean main")
    commit = git("rev-parse", "HEAD")
    ensure(bool(re.fullmatch(r"[a-f0-9]{40}", commit)), "Invalid commit")
    print(f"DEV_SOURCE_COMMIT={commit}")
    return commit


def validate_log(root: Path, log: Path, commit: str) -> None:
    ensure(root.is_absolute() and root.parent == Path("/tmp")
           and REPLAY_NAME.fullmatch(root.name) is not None,
           "Only direct /tmp/tracker-freshenv570-* input allowed")
    owner_checked(root, directory=True, private=True)
    owner_checked(log, directory=False, private=True)
    lines = log.read_text(encoding="utf-8").splitlines()
    for marker in MARKERS:
        ensure(marker in lines, f"Missing replay success marker: {marker}")
    ensure(f"DEV_SOURCE_COMMIT={commit}" in lines
           and f"ISOLATED_ROOT={root}" in lines
           and f"ISOLATED_ARTIFACTS_RETAINED={root}" in lines,
           "Replay root or commit does not agree with successful log")
    results = [line for line in lines if line.startswith("FRESHENV_REPLAY=")]
    ensure(results == ["FRESHENV_REPLAY=SUCCESS"],
           "Expected exactly one successful replay outcome")
    ensure(not (root / "source").exists(),
           "Detached source worktree still present")


def verify_wheels(root: Path) -> dict[str, str]:
    wheelhouse, receipt = root / "wheelhouse", root / "wheel-sha256.txt"
    owner_checked(wheelhouse, directory=True, private=True)
    owner_checked(receipt, directory=False, private=True)
    baseline = json.loads(BASELINE.read_text(encoding="utf-8"))
    versions = baseline["package_versions"]
    expected = {canonicalize_name(name): str(version)
                for name, version in versions.items()}
    ensure(len(expected) == len(versions) == 44
           and expected.get("pip") == "25.1.1",
           "Expected exact 44-package baseline")
    wheel_paths = sorted(wheelhouse.iterdir())
    ensure(len(wheel_paths) == 44, "Wheelhouse is not exactly 44 files")
    resolved_versions, hashes = {}, {}
    for path in wheel_paths:
        ensure(path.suffix == ".whl" and path.is_file()
               and not path.is_symlink(), "Unexpected wheelhouse entry")
        name, version, _, _ = parse_wheel_filename(path.name)
        name = canonicalize_name(str(name))
        ensure(name not in resolved_versions, "Duplicate normalized wheel")
        resolved_versions[name] = str(version)
        hashes[path.name] = sha256(path)
    ensure(resolved_versions == expected, "Wheels differ from recorded baseline")
    saved = {}
    for line in receipt.read_text(encoding="utf-8").splitlines():
        value, sep, filename = line.partition("  ")
        ensure(bool(sep) and HASH.fullmatch(value) is not None
               and filename not in saved, "Malformed or repeated wheel hash")
        saved[filename] = value
    ensure(saved == hashes, "Wheel bytes disagree with SHA-256 receipt")
    return hashes


def browser_info(root: Path) -> tuple[list[Path], list[dict]]:
    metadata_path = root / (
        "venv/lib/python3.13/site-packages/playwright/driver/package/browsers.json"
    )
    ensure(metadata_path.is_file() and not metadata_path.is_symlink(),
           "Fresh Playwright metadata unavailable")
    values = json.loads(metadata_path.read_text(encoding="utf-8"))["browsers"]
    specs = {item["name"]: item for item in values}
    cache = root / "home/.cache/ms-playwright"
    owner_checked(cache, directory=True, private=False)
    directories, report = [], []
    for name, prefix in (
        ("chromium", "chromium"),
        ("chromium-headless-shell", "chromium_headless_shell"),
        ("ffmpeg", "ffmpeg"),
    ):
        item = specs.get(name)
        ensure(isinstance(item, dict)
               and str(item.get("revision", "")).isdigit(),
               f"Missing browser specification: {name}")
        dest = cache / f"{prefix}-{item['revision']}"
        ensure(dest.is_dir() and not dest.is_symlink() and any(dest.iterdir()),
               f"Missing browser contents: {name}")
        directories.append(dest)
        report.append({
            "name": name,
            "revision": str(item["revision"]),
            "version": item.get("browserVersion"),
            "folder": dest.name,
        })
    return directories, report


def tree(root: Path) -> dict[str, dict]:
    """Hash regular files; permit only relative symlinks staying inside tree."""
    root = root.resolve(strict=True)
    files = {}
    for current, dirs, names in os.walk(root, followlinks=False):
        for name in sorted(dirs + names):
            path = Path(current) / name
            relative = path.relative_to(root).as_posix()
            if path.is_symlink():
                target = Path(os.readlink(path))
                ensure(not target.is_absolute(),
                       "Browser bundle contains absolute symlink")
                resolved = (path.parent / target).resolve(strict=True)
                ensure(resolved.is_relative_to(root),
                       "Browser symlink escapes its archive subtree")
                files[relative] = {"link": str(target)}
            elif path.is_file():
                files[relative] = {
                    "sha256": sha256(path), "size": path.stat().st_size,
                }
            elif not path.is_dir():
                raise ArchiveError("Unsupported browser filesystem entry")
        dirs[:] = [d for d in dirs
                   if not (Path(current) / d).is_symlink()]
    return files


def replay_evidence(root: Path, log: Path, commit: str) -> dict:
    validate_log(root, log, commit)
    wheels = verify_wheels(root)
    browser_dirs, browsers = browser_info(root)
    browser_hashes = {p.name: tree(p) for p in browser_dirs}
    total = sum((root / "wheelhouse" / name).stat().st_size for name in wheels)
    total += sum(item["size"] for entries in browser_hashes.values()
                 for item in entries.values() if "size" in item)
    print("REPLAY_EVIDENCE=VERIFIED")
    print(f"WHEEL_HASHES_VERIFIED={len(wheels)}")
    print(f"BROWSER_REVISIONS_VERIFIED={len(browsers)}")
    print(f"ESTIMATED_ARTIFACT_BYTES={total}")
    return {
        "commit": commit, "wheel_hashes": wheels,
        "browser_paths": browser_dirs, "browser_specs": browsers,
        "browser_hashes": browser_hashes, "estimated_bytes": total,
    }


def host_facts() -> dict:
    os_info = {}
    os_release = Path("/etc/os-release")
    if os_release.is_symlink():
        os_release = Path("/usr/lib/os-release")
    if os_release.is_file() and not os_release.is_symlink():
        for line in os_release.read_text(encoding="utf-8").splitlines():
            name, sep, value = line.partition("=")
            if sep and name in ("ID", "VERSION_ID", "PRETTY_NAME"):
                os_info[name] = value.strip().strip('"')
    format_string = "$" + "{binary:Package}\t$" + "{Version}\n"
    try:
        result = subprocess.run(
            ["dpkg-query", "-W", "-f=" + format_string],
            text=True, capture_output=True, check=False,
        )
    except OSError:
        result = None
    packages_ok = result is not None and result.returncode == 0
    return {
        "python": platform.python_version(),
        "architecture": platform.machine(),
        "platform": platform.platform(),
        "glibc": platform.libc_ver(),
        "os": os_info,
        "os_package_inventory_available": packages_ok,
        "os_packages": result.stdout.splitlines() if packages_ok else [],
    }


def create_archive(root: Path, log: Path, evidence: dict) -> Path:
    ensure(ARCHIVES.parent == Path("/var/lib")
           and ARCHIVES.parent.is_dir() and not ARCHIVES.parent.is_symlink()
           and ARCHIVES.parent.stat().st_uid == 0,
           "Unexpected persistent archive parent")
    ensure(not ARCHIVES.is_symlink(), "Archive path is a symlink")
    ARCHIVES.mkdir(mode=0o700, exist_ok=True)
    owner_checked(ARCHIVES, directory=True, private=True)
    available = shutil.disk_usage(ARCHIVES).free
    ensure(available >= evidence["estimated_bytes"] + 256 * 1024 * 1024,
           "Insufficient free space for archive and safety margin")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    final = ARCHIVES / f"baseline-{evidence['commit'][:12]}-{stamp}"
    ensure(not final.exists(), "Archive already exists")
    staging = Path(tempfile.mkdtemp(prefix=".pending-", dir=ARCHIVES))
    staging.chmod(0o700)
    try:
        payload = staging / "payload"
        payload.mkdir(mode=0o700)
        shutil.copytree(root / "wheelhouse", payload / "wheelhouse")
        cached = payload / "ms-playwright"
        cached.mkdir(mode=0o700)
        for browser in evidence["browser_paths"]:
            shutil.copytree(browser, cached / browser.name, symlinks=True)
        shutil.copy2(root / "wheel-sha256.txt", payload / "wheel-sha256.txt")
        shutil.copy2(BASELINE, payload / BASELINE.name)
        shutil.copy2(CONSTRAINTS, payload / CONSTRAINTS.name)
        shutil.copy2(log, payload / "successful-replay.log")
        for browser in evidence["browser_paths"]:
            ensure(tree(cached / browser.name)
                   == evidence["browser_hashes"][browser.name],
                   "Browser archive copy changed")
        ensure({name: sha256(payload / "wheelhouse" / name)
                for name in evidence["wheel_hashes"]}
               == evidence["wheel_hashes"], "Wheel archive copy changed")
        manifest = {
            "schema_version": 1,
            "source_commit": evidence["commit"],
            "created_utc": datetime.now(timezone.utc).isoformat(),
            "browser_revisions": evidence["browser_specs"],
            "host": host_facts(),
            "payload": tree(payload),
        }
        manifest_file = staging / "manifest.json"
        manifest_file.write_text(json.dumps(manifest, sort_keys=True, indent=2) + "\n",
                                 encoding="utf-8")
        manifest_file.chmod(0o600)
        os.replace(staging, final)
    except BaseException:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    return final


def verify_archive(path: Path) -> None:
    owner_checked(path, directory=True, private=True)
    manifest_file = path / "manifest.json"
    owner_checked(manifest_file, directory=False, private=True)
    manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
    ensure(manifest.get("schema_version") == 1
           and isinstance(manifest.get("payload"), dict),
           "Unsupported archive manifest")
    actual = tree(path / "payload")
    ensure(actual == manifest["payload"],
           "Archive integrity verification failed")
    print(f"ARCHIVE_FILES_VERIFIED={len(actual)}")
    print("RECOVERY_ARCHIVE_VERIFIED=PASS")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--replay-root", type=Path)
    parser.add_argument("--replay-log", type=Path)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--verify-archive", type=Path,
                        help="Verify a retained archive by its file-hash manifest")
    args = parser.parse_args(argv)
    if args.verify_archive is not None:
        if args.execute or args.replay_root or args.replay_log:
            parser.error("--verify-archive cannot be combined with replay arguments")
        try:
            verify_archive(args.verify_archive)
            return 0
        except (ArchiveError, OSError, UnicodeError, ValueError) as exc:
            print(f"RECOVERY_ARCHIVE_VERIFIED=FAILED ({type(exc).__name__}: {exc})",
                  file=sys.stderr)
            return 1
    if args.replay_root is None or args.replay_log is None:
        parser.error("--replay-root and --replay-log are required")
    try:
        commit = preflight()
        evidence = replay_evidence(args.replay_root, args.replay_log, commit)
        if not args.execute:
            print("DRY_RUN=PASSED; --execute required to preserve")
            return 0
        target = create_archive(args.replay_root, args.replay_log, evidence)
        verify_archive(target)
        print(f"RECOVERY_ARCHIVE={target}")
        print("ARCHIVE_PRESERVATION=SUCCESS")
        return 0
    except (ArchiveError, OSError, UnicodeError, ValueError, subprocess.CalledProcessError) as exc:
        print(f"ARCHIVE_PRESERVATION=FAILED ({type(exc).__name__}: {exc})",
              file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
