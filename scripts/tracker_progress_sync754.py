#!/usr/bin/env python3
"""Release 754: private GitHub outbound-only progress snapshot + manual Export Now.

No data is read from production without separate config approval; never logs
tokens, server responses, JSON records, lab results or detailed exception text.
"""
from __future__ import annotations

import argparse
import base64
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import stat
import sys
import tempfile
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from app.progress_export754 import CATEGORIES, canonical, extract, semantic_digest

REPOSITORY = "rehmert/tracker-progress-data"
API = "https://api.github.com"
FILENAMES = {x: "latest/" + x + ".json" for x in CATEGORIES}
IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,79}$")
FORBIDDEN = {"notes", "note", "password", "token", "email", "vendor",
             "purchase", "original_name", "stored_name", "job_id", "verify_code",
             "source_vial_id", "prescriber", "address", "qr_value",
             "snapshot_json", "content_type", "sha256", "attachment"}
CONFIG_KEYS = {"schema_version", "repository", "days", "lab_allowlist",
               "medication_allowlist", "token_file", "prod_approved"}


def safe_private_file(path):
    path = Path(path).absolute()
    if path.is_symlink() or not path.is_file():
        raise ValueError("PRIVATE_FILE_UNAVAILABLE")
    st = path.stat()
    if not stat.S_ISREG(st.st_mode) or st.st_uid != os.geteuid() or (st.st_mode & 0o077):
        raise ValueError("PRIVATE_FILE_PERMISSIONS")
    return path


def config_from(path):
    config = json.loads(safe_private_file(path).read_text(encoding="utf-8"))
    if (not isinstance(config, dict) or set(config) != CONFIG_KEYS
            or config["schema_version"] != 1
            or config["repository"] != REPOSITORY
            or not isinstance(config["days"], int)
            or not 7 <= config["days"] <= 730
            or type(config["prod_approved"]) is not bool
            or type(config["token_file"]) is not str):
        raise ValueError("CONFIG_INVALID")
    for field in ("lab_allowlist", "medication_allowlist"):
        values = config[field]
        if (not isinstance(values, list) or not all(
                type(x) is str and 0 < len(x.strip()) < 120 for x in values)):
            raise ValueError("ALLOWLIST_INVALID")
    return config


def validate_datasets(datasets):
    if set(datasets) != set(CATEGORIES):
        raise ValueError("DATASETS_INVALID")
    mandatory = {"schema_version", "source_instance", "generated_at_utc",
                 "reporting_period", "classification", "data",
                 "completeness", "provenance"}
    for category, obj in datasets.items():
        if set(obj) != mandatory or obj["schema_version"] != "1":
            raise ValueError("SCHEMA_INVALID")
        if (not isinstance(obj["reporting_period"], dict) or
                set(obj["reporting_period"]) != {"from", "to"} or
                not isinstance(obj["data"], dict)
                or not isinstance(obj["completeness"], dict)
                or set(obj["completeness"]) != {
                    "observed_records", "reporting_days", "measurement_available"}
                or not isinstance(obj["provenance"], dict)
                or set(obj["provenance"]) != {
                    "history", "summaries", "body_composition"}):
            raise ValueError("SCHEMA_INVALID")
        def inspect(value):
            if isinstance(value, dict):
                for key, item in value.items():
                    if key.lower() in FORBIDDEN:
                        raise ValueError("FIELD_NOT_ALLOWLISTED")
                    inspect(item)
            elif isinstance(value, list):
                for item in value:
                    inspect(item)
            elif value is not None and type(value) not in (bool, int, float, str):
                raise ValueError("SCHEMA_INVALID")
        inspect(obj)
        # JSON numeric serialization strictly disallows infinity and NaN.
        canonical(obj)
    return True



def validate_schema(document, rule, *, path="root"):
    """Validate the deliberately small, published JSON-Schema v1 subset.

    Schema is pinned in source and only permits type/const/enum/required/
    properties/additionalProperties/items/minimum/maximum/date-time formats.
    No external dependency or network-based $ref resolution.
    """
    if "const" in rule and document != rule["const"]:
        raise ValueError("SCHEMA_INVALID")
    if "enum" in rule and document not in rule["enum"]:
        raise ValueError("SCHEMA_INVALID")
    allowed = rule.get("type")
    if isinstance(allowed, str):
        allowed = [allowed]
    fits = {"object": lambda x: isinstance(x, dict),
            "array": lambda x: isinstance(x, list),
            "string": lambda x: isinstance(x, str),
            "integer": lambda x: type(x) is int,
            "number": lambda x: type(x) in (int, float),
            "boolean": lambda x: type(x) is bool,
            "null": lambda x: x is None}
    if allowed and not any(fits[t](document) for t in allowed):
        raise ValueError("SCHEMA_INVALID")
    if isinstance(document, dict):
        fields = rule.get("properties", {})
        if not set(rule.get("required", [])).issubset(document):
            raise ValueError("SCHEMA_INVALID")
        if rule.get("additionalProperties") is False and set(document) - set(fields):
            raise ValueError("SCHEMA_INVALID")
        for key, child in document.items():
            if key in fields:
                validate_schema(child, fields[key], path=path+"."+key)
    elif isinstance(document, list) and "items" in rule:
        for child in document:
            validate_schema(child, rule["items"], path=path+"[]")
    elif isinstance(document, (int, float)) and type(document) is not bool:
        if "minimum" in rule and document < rule["minimum"]:
            raise ValueError("SCHEMA_INVALID")
        if "maximum" in rule and document > rule["maximum"]:
            raise ValueError("SCHEMA_INVALID")
    elif isinstance(document, str) and rule.get("format") in ("date", "date-time"):
        try:
            if rule["format"] == "date":
                from datetime import date
                date.fromisoformat(document)
            else:
                datetime.fromisoformat(document.replace("Z", "+00:00"))
        except ValueError:
            raise ValueError("SCHEMA_INVALID") from None


def _api(token, method, path, body=None):
    if not path.startswith("/") or "://" in path:
        raise ValueError("UNSAFE_API_PATH")
    payload = canonical(body) if body is not None else None
    request = Request(API + path, data=payload, method=method, headers={
        "Accept": "application/vnd.github+json",
        "Content-Type": "application/json",
        "Authorization": "Bearer " + token,
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "Tracker-Private-Progress-Exporter-754",
    })
    for attempt in range(3):
        try:
            with urlopen(request, timeout=20) as response:
                return json.loads(response.read(8 * 1024 * 1024))
        except HTTPError as err:
            if err.code not in (429, 500, 502, 503, 504) or attempt == 2:
                raise ValueError("GITHUB_HTTP_" + str(err.code)) from None
        except (TimeoutError, OSError, URLError):
            if attempt == 2:
                raise ValueError("GITHUB_NETWORK_UNAVAILABLE") from None
        time.sleep(min(4, 2**attempt))
    raise ValueError("GITHUB_RETRY_EXHAUSTED")


def repo_visibility(token):
    repo = _api(token, "GET", "/repos/" + REPOSITORY)
    if (repo.get("full_name") != REPOSITORY or
            repo.get("private") is not True or
            repo.get("visibility") != "private" or
            repo.get("default_branch") != "main" or
            repo.get("archived") is True):
        raise ValueError("DESTINATION_NOT_PRIVATE_OR_INVALID")
    return repo


def _git_blob_sha(body):
    return hashlib.sha1(b"blob " + str(len(body)).encode() + b"\x00" + body).hexdigest()


def publish(token, documents, digest):
    """Single fast-forward Git tree commit; no temp history or extra branches."""
    repo_visibility(token)
    root = "/repos/" + REPOSITORY
    current = _api(token, "GET", root + "/git/ref/heads/main")["object"]["sha"]
    commit = _api(token, "GET", root + "/git/commits/" + current)
    tree_sha = commit["tree"]["sha"]
    tree = _api(token, "GET", root + "/git/trees/" + tree_sha + "?recursive=1")
    existing = {x["path"]: x["sha"] for x in tree.get("tree", [])
                if x.get("type") == "blob"}
    # Do not make redundant commits if the semantic snapshot hasn't changed.
    try:
        manifest = _api(token, "GET", root + "/contents/manifest.json?ref=main")
        old = json.loads(base64.b64decode(manifest["content"]).decode("utf-8"))
        if old.get("content_sha256") == digest:
            return "UNCHANGED"
    except ValueError as exc:
        if str(exc) != "GITHUB_HTTP_404":
            raise
    changed = []
    for path, body in sorted(documents.items()):
        if not (path.startswith(("latest/", "schema/")) or path in ("README.md", "manifest.json")):
            raise ValueError("UNEXPECTED_UPLOAD_PATH")
        encoded = body.encode("utf-8")
        if existing.get(path) == _git_blob_sha(encoded):
            continue
        blob = _api(token, "POST", root + "/git/blobs", {
            "content": body, "encoding": "utf-8"})
        changed.append({"path": path, "mode": "100644", "type": "blob",
                        "sha": blob["sha"]})
    if not changed:
        return "UNCHANGED"
    repo_visibility(token)  # Fail closed if visibility changed during preparation.
    new_tree = _api(token, "POST", root + "/git/trees", {
        "base_tree": tree_sha, "tree": changed})["sha"]
    new_commit = _api(token, "POST", root + "/git/commits", {
        "message": "Update authorized Tracker progress snapshot",
        "tree": new_tree, "parents": [current]})["sha"]
    _api(token, "PATCH", root + "/git/refs/heads/main", {
        "sha": new_commit, "force": False})
    latest = _api(token, "GET", root + "/git/ref/heads/main")
    if latest["object"]["sha"] != new_commit:
        raise ValueError("GITHUB_REF_MISMATCH")
    return "UPDATED"


def documents_for(datasets, schema_text):
    digest = semantic_digest(datasets)
    period = datasets["overview"]["reporting_period"]
    files = {FILENAMES[k]: json.dumps(v, indent=2, sort_keys=True,
              ensure_ascii=True, allow_nan=False) + "\n" for k,v in datasets.items()}
    files["schema/progress-v1.schema.json"] = schema_text.rstrip() + "\n"
    files["README.md"] = (
        "# Tracker progress data (private)\n\n"
        "Generated outbound by Tracker. Observed progress snapshots and "
        "descriptive calculations, **not** a medical record. Read "
        "`manifest.json` for reporting period, generation time and list "
        "of category JSON files under `latest/`. All datasets contain "
        "schema_version, source_instance, reporting_period, completeness and "
        "provenance. A null value means not measured, unknown or unavailable; "
        "it never means a recorded zero.\n\n"
        "## Categories and fields\n\n"
        "- `overview`: current/28-day weight and summary counts.\n"
        "- `weight`: dated scale readings in lb, rolling 7/28-day "
        "per-reading averages, most recent averages and 7/28-day changes. "
        "First observed reading is the starting weight. Goal is null "
        "until Tracker stores one.\n"
        "- `body-measurements`: circumference, waist/height and BIA/DEXA "
        "placeholders; unsupported fields are empty/null. "
        "Never infer muscle change from BIA.\n"
        "- `workouts`: dates, completed vs in-progress status, machine-specific "
        "sets (lb/reps), working vs warm-up, volume (lb × reps) "
        "and best observed loads. Different machines are not interchangeable.\n"
        "- `nutrition`: one calendar day per row; energy in kcal, protein, "
        "carbohydrate and fat in grams, logged-food and nutrient-completeness "
        "counts, protein adherence when a recorded target exists. "
        "No logs are null, not zero.\n"
        "- `vitals`: recorded systolic/diastolic in mmHg and pulse in bpm.\n"
        "- `labs`: allowlisted dated analyte, numeric value, laboratory "
        "unit and reference limits; no source PDF or notes.\n"
        "- `interventions`: allowlisted medication schedule changes "
        "as recorded *plans*, not proof of administration.\n\n"
        "All source histories are time bounded, currently up to 730 days. "
        "The only unbounded lookup is the first recorded scale weight. "
        "The export never includes usernames, uploaded files, purchases, "
        "vendors, raw notes, COAs or prescription identifiers.\n\n"
        "Private GitHub access is the confidentiality boundary, not "
        "end-to-end encryption. Git history may retain previously "
        "overwritten records; changes to data access or retention "
        "require a separate reviewed repo lifecycle plan.\n")
    files["manifest.json"] = json.dumps({
        "schema_version": "1",
        "source_instance": datasets["overview"]["source_instance"],
        "generated_at_utc": datasets["overview"]["generated_at_utc"],
        "reporting_period": period,
        "content_sha256": digest,
        "files": sorted(FILENAMES.values()),
        "retention_policy": "bounded-window; Git history still retains past commits",
    }, indent=2, sort_keys=True) + "\n"
    return files, digest


def _status_file(directory, status, successful_at=None):
    target = directory / "status.json"
    if successful_at is None and target.is_file() and not target.is_symlink():
        try:
            previous = json.loads(target.read_text())
            successful_at = previous.get("last_success_utc")
        except (ValueError, OSError):
            successful_at = None
    stale = True
    if successful_at:
        try:
            previous_time = datetime.fromisoformat(successful_at.replace("Z", "+00:00"))
            stale = (datetime.now(timezone.utc) - previous_time).total_seconds() > 48*3600
        except ValueError:
            pass
    doc = {"status": status, "last_success_utc": successful_at,
           "stale": stale}
    with tempfile.NamedTemporaryFile("w", dir=directory, prefix=".status-",
                                     delete=False, encoding="utf-8") as file:
        temp = Path(file.name)
        os.chmod(temp, 0o600)
        json.dump(doc, file, sort_keys=True)
    os.replace(temp, target)


def run(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    parser.add_argument("--db", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--source", required=True, choices=("synthetic", "live"))
    parser.add_argument("--sync", action="store_true",
                        help="Outbound upload to private GitHub only")
    args = parser.parse_args(argv)
    try:
        config = config_from(args.config)
        instance = os.environ.get("TRACKER_INSTANCE", "").upper()
        if args.source == "synthetic":
            if instance != "DEV":
                raise ValueError("SYNTHETIC_EXPORT_DEV_ONLY")
            label = "DEV-SYNTHETIC"
            if Path(args.db).resolve() == Path("/opt/tracker/data/tracker.db").resolve():
                raise ValueError("DEV_SYNTHETIC_MUST_NOT_USE_LIVE_DB")
        else:
            if instance != "PROD" or config["prod_approved"] is not True:
                raise ValueError("PROD_EXPORT_NOT_AUTHORIZED")
            if Path(args.db).resolve() != Path("/opt/tracker/data/tracker.db").resolve():
                raise ValueError("UNEXPECTED_PROD_DATABASE")
            label = "PROD"
        output = Path(args.output).absolute()
        if output.is_symlink():
            raise ValueError("UNSAFE_OUTPUT_DIRECTORY")
        output.mkdir(mode=0o700, parents=True, exist_ok=True)
        if (output.stat().st_uid != os.geteuid()
                or output.stat().st_mode & 0o077):
            raise ValueError("OUTPUT_NOT_PRIVATE")
        docs = extract(Path(args.db), instance=label, days=config["days"],
                       lab_allowlist=config["lab_allowlist"],
                       medication_allowlist=config["medication_allowlist"])
        validate_datasets(docs)
        schema_text = (Path(__file__).resolve().parents[1] /
                       "app/progress_schema754.json").read_text()
        schema = json.loads(schema_text)
        if schema.get("title") != "Tracker progress snapshot v1":
            raise ValueError("SCHEMA_INVALID")
        for doc in docs.values():
            validate_schema(doc, schema)
        documents, digest = documents_for(docs, schema_text)
        with tempfile.TemporaryDirectory(prefix=".progress-", dir=output) as scratch:
            folder = Path(scratch)
            for name, body in documents.items():
                path = folder / name
                path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
                path.write_text(body)
                path.chmod(0o600)
            # Make only the manifest+latest bundle visible locally after full validation.
            # Actual data publication happens atomically in a single Git tree commit.
            if args.sync:
                token = safe_private_file(config["token_file"]).read_text().strip()
                if not token or any(x.isspace() for x in token):
                    raise ValueError("GITHUB_CREDENTIAL_INVALID")
                result = publish(token, documents, digest)
            else:
                result = "LOCAL_VALIDATED"
        last = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00","Z")
        _status_file(output, "successful" if args.sync else "local_validated",
                     last if args.sync else None)
        print("PROGRESS_754_STATUS=" + result)
        print("PROGRESS_754_SCHEMA=VALIDATED")
        print("PROGRESS_754_DATA_SOURCE=" + label)
        return 0
    except (ValueError, RuntimeError, OSError, sqlite3.Error, UnicodeError,
            TypeError, KeyError, json.JSONDecodeError) as exc:
        # A failed attempt must not destroy the previous success timestamp.
        if "output" in locals() and output.is_dir() and not output.is_symlink():
            try:
                _status_file(output, "failed")
            except (OSError, ValueError):
                pass
        # Do not print raw SQLite errors, URL response bodies or identifying data.
        code = str(exc)
        if not re.fullmatch("[A-Z0-9_]{4,80}", code):
            code = "EXPORT_FAILED"
        print("PROGRESS_754_ERROR=" + code, file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(run())
