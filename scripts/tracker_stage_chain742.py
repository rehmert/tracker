#!/usr/bin/env python3
"""Release 742 fail-closed *read-only* DEV→PROD receipt-chain verifier.

Important distinction: a DEV qualification/install base MAY differ from the
currently installed PROD base during a cumulative DEV-ahead-of-PROD promotion.
Both bases must independently be ancestors of the exact target; signed approval,
installed host checks, command deduplication and rollback remain the external
release agent's responsibility. This is an executable contract/handoff, not
a replacement or silent modification of the host-side agent.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import subprocess
import sys

SHA = re.compile(r"[0-9a-f]{40}\Z")
REQUEST = re.compile(r"[A-Za-z0-9_-]{4,90}\Z")
STAGES = ("qualify", "dev_install", "prod_preflight", "prod_deploy")
RECEIPT_LIMIT = 16 * 1024


class StageChainError(ValueError):
    pass


def require_sha(value: object) -> str:
    if not isinstance(value, str) or not SHA.fullmatch(value):
        raise StageChainError("Expected exact 40-digit git SHA")
    return value


def parse_receipt(path: Path) -> dict:
    if path.is_symlink() or not path.is_file() or path.stat().st_size > RECEIPT_LIMIT:
        raise StageChainError("Missing, linked or oversized immutable receipt")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or data.get("schema") != 1:
        raise StageChainError("Invalid receipt schema")
    for field in ("target", "base"):
        require_sha(data.get(field))
    if not isinstance(data.get("request_id"), str) or not REQUEST.fullmatch(data["request_id"]):
        raise StageChainError("Malformed receipt request ID")
    if not isinstance(data.get("markers"), list) or not all(
        isinstance(x, str) and len(x) <= 200 for x in data["markers"]
    ):
        raise StageChainError("Malformed receipt markers")
    if data.get("status") != "passed" or data.get("exit_code") != 0:
        raise StageChainError("Prior stage did not pass")
    return data


def git_ancestor(git_root: Path, base: str, target: str) -> bool:
    result = subprocess.run(
        ["git", "-C", str(git_root), "merge-base", "--is-ancestor", base, target],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False,
    )
    return result.returncode == 0


def verify(receipts: dict[str, dict], *, release: int, ref: str, target: str,
           prod_base: str, main: str, ancestor=git_ancestor,
           git_root: Path | None = None) -> dict:
    target = require_sha(target)
    prod_base = require_sha(prod_base)
    main = require_sha(main)
    if not isinstance(release, int) or release < 1:
        raise StageChainError("Invalid release number")
    if not isinstance(ref, str) or not re.fullmatch(r"release/[0-9]+-[a-z0-9-]{3,100}", ref):
        raise StageChainError("Invalid release source ref")
    if main not in (prod_base, target):
        raise StageChainError("GitHub main drifted from approved PROD base/target")
    names = list(receipts)
    if names != list(STAGES[:len(names)]) or len(names) < 2:
        raise StageChainError("Receipts must form contiguous qualify→install→preflight→deploy stages")
    seen: set[str] = set()
    previous_id: str | None = None
    previous_finished = None
    dev_base = None
    for action in names:
        item = receipts[action]
        if (item.get("schema") != 1 or item.get("action") != action
                or item.get("release") != release
                or item.get("ref") != ref or item.get("status") != "passed"
                or item.get("exit_code") != 0
                or item.get("target") != target):
            raise StageChainError("Receipt stage, release, ref, status or target mismatch")
        rid = item.get("request_id")
        if not isinstance(rid, str) or not REQUEST.fullmatch(rid) or rid in seen:
            raise StageChainError("Duplicate or invalid immutable request ID")
        seen.add(rid)
        if item.get("previous_request_id") != previous_id:
            raise StageChainError("Missing or incorrect previous successful stage")
        if not isinstance(item.get("markers"), list):
            raise StageChainError("Missing immutable stage markers")
        marker = {
            "qualify": f"RELEASE_{release}_QUALIFICATION=PASSED_SCOPED_NO_DEPLOY",
            "dev_install": f"RELEASE_{release}_DEV_INSTALL=SUCCESS",
            "prod_preflight": "PREFLIGHT=PASSED",
            "prod_deploy": "PROD_INSTALLED_COMMIT="+target,
        }[action]
        if marker not in item["markers"]:
            raise StageChainError("Stage-specific success marker is missing")
        if action == "prod_deploy":
            if "DEV_CONTROLLED_RELEASE=SUCCESS" not in item["markers"]:
                raise StageChainError("DEV-controlled live deployment not verified")
            if main != target:
                raise StageChainError("GitHub main not promoted to exact target")
        if action in ("qualify", "dev_install"):
            if dev_base is None:
                dev_base = require_sha(item.get("base"))
            elif item.get("base") != dev_base:
                raise StageChainError("Qualification/install base differs")
        elif item.get("base") != prod_base:
            raise StageChainError("PROD stage not pinned to installed PROD base")
        stamp = item.get("finished_at_utc")
        if not isinstance(stamp, str):
            raise StageChainError("Missing completion time")
        try:
            finished = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
        except ValueError:
            raise StageChainError("Malformed completion time") from None
        if finished.tzinfo is None:
            raise StageChainError("Completion time lacks timezone")
        if previous_finished is not None and finished < previous_finished:
            raise StageChainError("Stage finished before predecessor")
        previous_finished = finished
        previous_id = rid
    # Both independently require valid ancestry. DEV base != PROD base is
    # permitted: otherwise legitimate accumulated DEV releases are blocked.
    if git_root is None:
        git_root = Path(__file__).resolve().parents[1]
    if not ancestor(git_root, dev_base, target):
        raise StageChainError("DEV qualification base is not target ancestor")
    if not ancestor(git_root, prod_base, target):
        raise StageChainError("PROD installed base is not target ancestor")
    return {
        "schema": 1,
        "chain": "PASS",
        "release": release,
        "verified_stages": names,
        "dev_base_differs_from_prod": dev_base != prod_base,
        "both_bases_ancestors_of_target": True,
        "live_agent_stage_chain_modified": False,
        "external_approval_and_host_checks_still_required": True,
    }


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--release", type=int, required=True)
    p.add_argument("--ref", required=True)
    p.add_argument("--target", required=True)
    p.add_argument("--prod-base", required=True)
    p.add_argument("--main-sha", required=True)
    p.add_argument("--git-root", type=Path, default=Path(__file__).resolve().parents[1])
    p.add_argument("--qualify", type=Path, required=True)
    p.add_argument("--dev-install", type=Path, required=True)
    p.add_argument("--prod-preflight", type=Path)
    p.add_argument("--prod-deploy", type=Path)
    args = p.parse_args(argv)
    try:
        if args.prod_deploy and not args.prod_preflight:
            raise StageChainError("Deployment cannot skip passed preflight")
        staged = [
            ("qualify", args.qualify), ("dev_install", args.dev_install),
            ("prod_preflight", args.prod_preflight),
            ("prod_deploy", args.prod_deploy),
        ]
        rows = {action: parse_receipt(path) for action, path in staged if path is not None}
        result = verify(
            rows, release=args.release, ref=args.ref, target=args.target,
            prod_base=args.prod_base, main=args.main_sha, git_root=args.git_root,
        )
    except (StageChainError, OSError, ValueError, TypeError, KeyError) as err:
        print("RELEASE_742_STAGE_CHAIN=BLOCKED_"+type(err).__name__, file=sys.stderr)
        return 2
    print(json.dumps(result, sort_keys=True))
    print("RELEASE_742_STAGE_CHAIN=VERIFIED_READ_ONLY")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
