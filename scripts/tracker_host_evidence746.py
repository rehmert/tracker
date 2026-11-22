#!/usr/bin/env python3
"""Release 746: read-only sanitized browser/OS shared-library evidence.

Complements the 569 observed Python pins and 705 offline wheel replay.
No installs, downloads, package resolver, process introspection or execution.
Cannot certify that all transitive system libraries are captured or that
a rollback was actually performed.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import stat
import sys

from scripts.tracker_browser_provenance743 import snapshot as browser_snapshot
from scripts.tracker_dependency_baseline569 import read_manifest, BASELINE

HEX = re.compile(r"[0-9a-f]{64}\Z")
NAME = re.compile(r"[A-Za-z0-9._+-]{1,120}\Z")
MAX_BYTES = 4096 * 1024 * 1024
MAX_LIBRARIES = 128


class EvidenceError(ValueError):
    pass


def file_digest(path: Path):
    if path.is_symlink():
        raise EvidenceError("Symlinked library or browser path")
    st = path.stat()
    if (not stat.S_ISREG(st.st_mode) or not 1 <= st.st_size <= MAX_BYTES):
        raise EvidenceError("Expected nonempty regular library")
    h = sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            h.update(chunk)
    after = path.stat()
    if (after.st_size, after.st_mtime_ns, after.st_ino) != (
            st.st_size, st.st_mtime_ns, st.st_ino):
        raise EvidenceError("File mutated during read")
    return {"sha256": h.hexdigest(), "bytes": st.st_size}


def libraries_snapshot(paths: list[Path]) -> dict:
    if not paths or len(paths) > MAX_LIBRARIES:
        raise EvidenceError("Explicit nonempty bounded library list required")
    result = {}
    for path in paths:
        if not path.is_absolute() or not NAME.fullmatch(path.name):
            raise EvidenceError("Invalid shared library name")
        if path.name in result:
            raise EvidenceError("Duplicate or colliding library identity")
        result[path.name] = file_digest(path)
    return dict(sorted(result.items()))


def snapshot(browser: Path, libraries: list[Path]) -> dict:
    baseline = read_manifest(BASELINE)
    recorded = browser_snapshot(browser)
    if (recorded["python"] != baseline["python"] or
            recorded["playwright"] != baseline["packages"]["playwright"]):
        raise EvidenceError("Runtime deviates from observed pinned baseline")
    report = {
        "schema": 1,
        "python": recorded["python"],
        "playwright": recorded["playwright"],
        "os_id": recorded["os_id"],
        "os_version": recorded["os_version"],
        "libc_name": recorded["libc_name"],
        "libc_version": recorded["libc_version"],
        "chromium_sha256": recorded["chromium_sha256"],
        "chromium_bytes": recorded["chromium_bytes"],
        "libraries": libraries_snapshot(libraries),
        "scope": "explicit library list only; no rollback or transitive completeness",
    }
    validate(report)
    return report


def validate(report: dict) -> dict:
    fields = {"schema","python","playwright","os_id","os_version",
              "libc_name","libc_version","chromium_sha256",
              "chromium_bytes","libraries","scope"}
    if not isinstance(report, dict) or set(report) != fields or report["schema"] != 1:
        raise EvidenceError("Invalid system evidence fields")
    if report["scope"] != "explicit library list only; no rollback or transitive completeness":
        raise EvidenceError("Invalid evidence scope")
    baseline = read_manifest(BASELINE)
    if (report["python"] != baseline["python"] or
            report["playwright"] != baseline["packages"]["playwright"]):
        raise EvidenceError("Python/Playwright not pinned")
    if not isinstance(report["chromium_sha256"], str) or not HEX.fullmatch(report["chromium_sha256"]):
        raise EvidenceError("Bad Chromium digest")
    for field in ("python","playwright","os_id","os_version","libc_name","libc_version"):
        value = report[field]
        if not isinstance(value, str) or not re.fullmatch(r"[a-zA-Z0-9_.+-]{1,80}",value):
            raise EvidenceError("Invalid OS/runtime identity")
    count = report["chromium_bytes"]
    if type(count) is not int or not 1 <= count <= MAX_BYTES:
        raise EvidenceError("Invalid Chromium bytes")
    libs=report["libraries"]
    if not isinstance(libs, dict) or not 1 <= len(libs) <= MAX_LIBRARIES:
        raise EvidenceError("Missing bounded libraries")
    for name,item in libs.items():
        if not isinstance(name,str) or not NAME.fullmatch(name) or not isinstance(item,dict):
            raise EvidenceError("Invalid library entry")
        if set(item)!={"sha256","bytes"} or not isinstance(item["sha256"],str) or not HEX.fullmatch(item["sha256"]):
            raise EvidenceError("Invalid library hash")
        if type(item["bytes"]) is not int or not 1 <= item["bytes"] <= MAX_BYTES:
            raise EvidenceError("Invalid library size")
    return report


def compare(left: dict, right: dict) -> dict:
    validate(left);validate(right)
    return {
        "schema": 1,
        "host_evidence_matches": left == right,
        "library_names_match": set(left["libraries"]) == set(right["libraries"]),
        "library_count": len(left["libraries"]),
        "python_wheels_replayed_by_this_check": False,
        "full_elf_dependency_closure_certified": False,
        "browser_http_https_compatibility_certified": False,
        "os_library_rollback_tested": False,
        "dependency_update_authorized": False,
    }


def private_read(path: Path) -> dict:
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 40000:
        raise EvidenceError("Invalid private evidence file")
    if path.stat().st_mode & 0o077:
        raise EvidenceError("Evidence file must be private")
    return validate(json.loads(path.read_text(encoding="utf-8")))


def private_write(path: Path, record: dict) -> None:
    directory=path.parent
    if (not directory.is_dir() or directory.is_symlink() or
            not directory.resolve().is_relative_to(Path("/tmp")) or
            directory.stat().st_mode & 0o077):
        raise EvidenceError("Evidence output requires private /tmp directory")
    contents=json.dumps(validate(record),sort_keys=True,indent=2).encode()+b"\n"
    fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|getattr(os,"O_NOFOLLOW",0),0o600)
    with os.fdopen(fd,"wb") as stream:
        stream.write(contents)
        stream.flush()
        os.fsync(stream.fileno())


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    modes=p.add_mutually_exclusive_group(required=True)
    modes.add_argument("--capture",type=Path)
    modes.add_argument("--compare",nargs=2,type=Path,metavar=("DEV","PROD"))
    p.add_argument("--library",type=Path,action="append",default=[])
    p.add_argument("--output",type=Path)
    p.add_argument("--require-complete",action="store_true")
    a=p.parse_args(argv)
    if a.capture and not a.output:
        p.error("Capture requires private --output")
    if a.compare and (a.library or a.output):
        p.error("Comparisons read pre-existing private evidence only")
    try:
        if a.capture is not None:
            result=snapshot(a.capture,a.library)
            private_write(a.output,result)
        else:
            result=compare(*(private_read(path) for path in a.compare))
            print(json.dumps(result,sort_keys=True))
            if not result["host_evidence_matches"]:
                return 2
    except (OSError,ValueError,TypeError,KeyError) as exc:
        print("DEPENDENCY_746_EVIDENCE=ERROR_"+type(exc).__name__,file=sys.stderr)
        return 2
    if a.require_complete:
        print("DEPENDENCY_746_COMPLETION=BLOCKED_NEEDS_REVIEWED_OFFLINE_BROWSER_OS_ROLLBACK")
        return 3
    print("DEPENDENCY_746_EVIDENCE=PASS_SCOPED_NOT_CERTIFICATION")
    return 0


if __name__=="__main__":
    raise SystemExit(main())
