#!/usr/bin/env python3
"""Release 744: fail-closed, read-only command coordination for parallel Work tasks.

Does not write requests, repositories, installed services or private data.
All callers must re-read authoritative GitHub records before CAS update_file.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys

SHA = re.compile(r"[0-9a-f]{40}\Z")
ID = re.compile(r"r[1-9][0-9]{0,5}-[a-z0-9]{8,20}\Z")
REF = re.compile(r"release/([1-9][0-9]{0,5})-[a-z0-9-]+\Z")
STAGES = ("qualify", "dev_install", "prod_preflight", "prod_deploy")
FIELDS = ("schema", "request_id", "action", "release", "target", "base",
          "ref", "previous_request_id")


class Blocked(ValueError):
    pass


def require(condition, reason):
    if not condition:
        raise Blocked(reason)


def validate(row):
    require(isinstance(row, dict) and set(row) == set(FIELDS),
            "invalid_command_schema")
    require(row["schema"] == 1 and row["action"] in STAGES,
            "invalid_action")
    n = row["release"]
    require(type(n) is int and 1 <= n <= 999999, "invalid_release")
    require(isinstance(row["request_id"], str) and ID.fullmatch(row["request_id"]),
            "invalid_request_id")
    for name in ("target", "base"):
        require(isinstance(row[name], str) and SHA.fullmatch(row[name]),
                "invalid_"+name)
    require(row["target"] != row["base"], "same_base_and_target")
    name = row["ref"]
    match = REF.fullmatch(name) if isinstance(name, str) else None
    require(match is not None and int(match.group(1)) == n, "invalid_release_ref")
    previous = row["previous_request_id"]
    require(previous is None or (isinstance(previous, str) and ID.fullmatch(previous)),
            "invalid_predecessor_id")
    require((row["action"] == "qualify") == (previous is None),
            "stage_predecessor_missing")
    return row


def verify_receipt(command, receipt, passed=True):
    require(isinstance(receipt, dict), "missing_receipt")
    require(all(receipt.get(field) == command[field] for field in FIELDS),
            "receipt_mismatch")
    status = receipt.get("status")
    require(status in ("passed", "failed", "blocked", "unknown"),
            "invalid_receipt_status")
    if passed:
        require(status == "passed" and receipt.get("exit_code") == 0,
                "receipt_not_passed")
        markers = receipt.get("markers")
        require(isinstance(markers, list), "missing_receipt_markers")
        n, target = command["release"], command["target"]
        marker = {
            "qualify": f"RELEASE_{n}_QUALIFICATION=PASSED_SCOPED_NO_DEPLOY",
            "dev_install": f"RELEASE_{n}_DEV_INSTALL=SUCCESS",
            "prod_preflight": "PREFLIGHT=PASSED",
            "prod_deploy": "PROD_INSTALLED_COMMIT="+target,
        }[command["action"]]
        require(marker in markers, "missing_success_marker")
        if command["action"] == "prod_deploy":
            require("DEV_CONTROLLED_RELEASE=SUCCESS" in markers,
                    "missing_deployment_verification")


def assess(current, latest, candidate, *, current_receipt=None,
           main_sha, dev_sha, branch_sha, prod_authorized=False):
    """Return a safe one-stage transition or raise Blocked.

    The caller still MUST refetch command, receipt and branch before writing
    and use the exact current content blob SHA with GitHub update_file.
    """
    current = validate(current)
    candidate = validate(candidate)
    require(isinstance(latest, dict), "missing_latest")
    prior = validate({name: latest.get(name) for name in FIELDS})
    for label, value in (("main", main_sha), ("dev", dev_sha),
                         ("branch", branch_sha)):
        require(isinstance(value, str) and SHA.fullmatch(value),
                "invalid_"+label+"_sha")
    require(candidate["target"] == branch_sha, "target_branch_drift")
    require(candidate["request_id"] not in (current["request_id"], prior["request_id"]),
            "duplicate_request")
    if candidate["action"] in ("prod_preflight", "prod_deploy"):
        require(prod_authorized, "explicit_prod_authorization_required")
    if current["request_id"] != prior["request_id"]:
        # 743 safety hold rewound current to previously passed DEV installation
        # after a verified successful PROD deployment. Reconcile ONLY when
        # starting the next release, never when repeating a completed stage.
        verify_receipt(current, current_receipt)
        verify_receipt(prior, latest)
        require(prior["action"] == "prod_deploy" and
                current["release"] == prior["release"] and
                current["ref"] == prior["ref"] and
                current["target"] == prior["target"] and
                STAGES.index(current["action"]) < STAGES.index(prior["action"]) and
                main_sha == prior["target"] and dev_sha == prior["target"] and
                candidate["release"] == prior["release"] + 1 and
                candidate["action"] == "qualify", "pending_or_stale_conflict")
    else:
        verify_receipt(prior, latest, passed=False)
    state = latest.get("status")
    if state == "passed":
        verify_receipt(prior, latest)
        if candidate["action"] == "qualify":
            require(prior["action"] in ("dev_install", "prod_deploy"),
                    "unfinished_previous_release")
            require(candidate["release"] == prior["release"]+1 and
                    candidate["base"] == prior["target"] and
                    dev_sha == prior["target"], "new_release_baseline_mismatch")
            if prior["action"] == "prod_deploy":
                require(main_sha == prior["target"], "prod_main_drift")
            return "NEW_RELEASE"
        i = STAGES.index(prior["action"])+1
        require(i < 4 and candidate["action"] == STAGES[i] and
                candidate["release"] == prior["release"] and
                candidate["target"] == prior["target"] and
                candidate["ref"] == prior["ref"] and
                candidate["previous_request_id"] == prior["request_id"],
                "nonsequential_stage_or_target")
        expected_base = main_sha if candidate["action"] == "prod_preflight" else prior["base"]
        require(candidate["base"] == expected_base, "base_mismatch")
        if candidate["action"] == "dev_install":
            require(dev_sha == prior["base"], "installed_dev_drift")
        else:
            require(dev_sha == prior["target"] and main_sha == candidate["base"],
                    "installed_host_drift")
        return "NEXT_STAGE"
    if state == "failed":
        require(prior["action"] == "qualify" and candidate["action"] == "qualify" and
                candidate["release"] == prior["release"] and
                candidate["ref"] == prior["ref"] and
                candidate["base"] == prior["base"] and
                candidate["target"] != prior["target"] and
                dev_sha == prior["base"], "failed_live_or_unchanged_qualification")
        return "NEW_SHA_QUALIFICATION"
    if state == "blocked" and latest.get("failure_category") == "StageChainBlocked":
        require(candidate["action"] != "qualify" and
                all(candidate[name] == prior[name] for name in
                    ("action", "release", "target", "base", "ref", "previous_request_id")),
                "invalid_chain_block_retry")
        if candidate["action"] in ("prod_preflight", "prod_deploy"):
            require(dev_sha == candidate["target"] and
                    main_sha == candidate["base"], "installed_host_drift")
        return "NONEXECUTED_CHAIN_RETRY"
    raise Blocked("unknown_or_nonrecoverable_stage")


def blob_sha(contents):
    return hashlib.sha1(b"blob "+str(len(contents)).encode()+b"\0"+contents).hexdigest()


def read_json(path):
    require(not path.is_symlink() and path.is_file() and
            0 < path.stat().st_size <= 16384, "unsafe_input")
    raw = path.read_bytes()
    value = json.loads(raw)
    require(isinstance(value, dict), "invalid_json_object")
    return value, blob_sha(raw)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    for name in ("current", "latest", "candidate"):
        p.add_argument("--"+name, type=Path, required=True)
    p.add_argument("--current-receipt", type=Path)
    for name in ("main-sha", "dev-sha", "branch-sha",
                 "expected-current-blob", "expected-latest-id"):
        p.add_argument("--"+name, required=True)
    p.add_argument("--prod-authorized", action="store_true")
    a = p.parse_args(argv)
    try:
        current, current_blob = read_json(a.current)
        latest, _ = read_json(a.latest)
        candidate, _ = read_json(a.candidate)
        older = read_json(a.current_receipt)[0] if a.current_receipt else None
        require(a.expected_current_blob == current_blob, "control_blob_drift")
        require(a.expected_latest_id == latest.get("request_id"), "receipt_snapshot_drift")
        decision = assess(current, latest, candidate, current_receipt=older,
                          main_sha=a.main_sha, dev_sha=a.dev_sha,
                          branch_sha=a.branch_sha, prod_authorized=a.prod_authorized)
    except (Blocked, OSError, ValueError, TypeError, KeyError) as exc:
        label = str(exc) if isinstance(exc, Blocked) else type(exc).__name__
        print("RELEASE_744_COORDINATION=BLOCKED_"+label, file=sys.stderr)
        return 2
    print("RELEASE_744_COORDINATION=ALLOW_"+decision)
    print("RELEASE_744_CAS_BLOB="+current_blob)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
