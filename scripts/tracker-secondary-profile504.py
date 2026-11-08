#!/usr/bin/env python3
"""Profile isolated Release 440 secondary workflow and readiness HTTP tests.

Diagnostics only. Does not change production routes, fixtures, security checks,
or test assertions. Run exclusively from a disposable candidate worktree on
tracker-dev; pytest's conftest creates an independent temporary database.
Only HTTP method, route path, status and timings are reported. No credentials,
cookies, query strings, request bodies, or response content are logged.
"""

from __future__ import annotations

import argparse
import os
import re
import socket
import subprocess
import sys
import time
from collections import defaultdict
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]

TARGETS = {
    "workflow": (
        "tests/test_secondary_private_workflow440.py::"
        "test_full_private_browser_workflow_with_audits_and_no_cross_account_data"
    ),
    "readiness": (
        "tests/test_secondary_integration440.py::"
        "test_authenticated_readiness_matches_every_runtime_flag"
    ),
}


IMPORT_TIME_RE = re.compile(
    r"^import time:\s*(\d+)\s*\|\s*(\d+)\s*\|\s*(.+)$"
)


def parse_import_time(stderr: str) -> list[tuple[str, int, int]]:
    """Read only module names and durations, ignoring all other child output."""
    rows = []
    for line in stderr.splitlines():
        match = IMPORT_TIME_RE.fullmatch(line)
        if match is not None:
            module = match.group(3).strip()
            if re.fullmatch(r"[A-Za-z0-9_.]+", module):
                rows.append(
                    (module, int(match.group(1)), int(match.group(2)))
                )
    return rows


def worker_command(args: object) -> str | None:
    """Identify known private worker subprocesses without recording arguments."""
    if not isinstance(args, (tuple, list)):
        return None
    if "-m" not in args:
        return None
    index = args.index("-m") + 1
    if index >= len(args):
        return None
    module = args[index]
    if isinstance(module, str) and module.startswith("app.worker_"):
        return module
    return None


class TimingRecorder:
    def __init__(self, *, import_sample: bool = False):
        self.requests: list[tuple[str, str, int | str, float]] = []
        self.workers: list[tuple[str, float]] = []
        self.import_sample = import_sample
        self.import_samples: dict[
            str, list[tuple[str, int, int]]
        ] = {}
        self._request = None
        self._run = None

    def install(self):
        import httpx

        self._request = httpx.Client.request
        self._run = subprocess.run
        recorded_requests = self.requests
        recorded_workers = self.workers
        original_request = self._request
        original_run = self._run

        def timed_request(client, method, url, *args, **kwargs):
            route = urlsplit(str(url)).path
            if not route.startswith("/secondary/"):
                return original_request(client, method, url, *args, **kwargs)
            began = time.perf_counter()
            status: int | str = "EXCEPTION"
            try:
                response = original_request(client, method, url, *args, **kwargs)
                status = response.status_code
                return response
            finally:
                recorded_requests.append((
                    str(method).upper(),
                    route,
                    status,
                    time.perf_counter() - began,
                ))

        def timed_run(*args, **kwargs):
            command = args[0] if args else kwargs.get("args")
            module = worker_command(command)
            if module is None:
                return original_run(*args, **kwargs)

            # Instrument only the first subprocess of each distinct module.
            # No worker body, environment, IPC payload or security condition
            # is modified. CPython prints import timings on captured stderr.
            # These sampled calls run slower: do not compare their wall time
            # with a normal benchmark.
            sample = (
                self.import_sample and module not in self.import_samples
                and isinstance(command, (list, tuple))
                and len(command) >= 3
                and command[1] == "-m"
                and isinstance(command[0], str)
            )
            if sample:
                self.import_samples[module] = []
                modified_command = [
                    command[0], "-X", "importtime", *command[1:]
                ]
                if args:
                    args = (modified_command, *args[1:])
                else:
                    kwargs = {**kwargs, "args": modified_command}

            began = time.perf_counter()
            try:
                result = original_run(*args, **kwargs)
                if sample and isinstance(
                    getattr(result, "stderr", None), str
                ):
                    self.import_samples[module] = parse_import_time(
                        result.stderr
                    )
                return result
            finally:
                recorded_workers.append(
                    (module, time.perf_counter() - began)
                )

        httpx.Client.request = timed_request
        subprocess.run = timed_run

    def uninstall(self):
        import httpx

        if self._request is not None:
            httpx.Client.request = self._request
        if self._run is not None:
            subprocess.run = self._run

    def report(self):
        print("=== SECONDARY HTTP REQUEST TIMINGS (SLOWEST FIRST) ===", flush=True)
        for method, route, status, seconds in sorted(
            self.requests, key=lambda item: item[3], reverse=True
        ):
            print(
                f"SECONDARY_HTTP method={method} path={route} "
                f"status={status} seconds={seconds:.3f}",
                flush=True,
            )
        print("=== SECONDARY REQUEST SUMMARY ===", flush=True)
        print(
            f"SECONDARY_HTTP_COUNT={len(self.requests)} "
            f"TOTAL_SECONDS={sum(row[3] for row in self.requests):.3f}",
            flush=True,
        )
        groups = defaultdict(lambda: [0, 0.0])
        for _, route, _, duration in self.requests:
            group = groups[route]
            group[0] += 1
            group[1] += duration
        for route, (count, total) in sorted(
            groups.items(), key=lambda row: row[1][1], reverse=True
        ):
            print(
                f"SECONDARY_ROUTE path={route} count={count} "
                f"total_seconds={total:.3f}",
                flush=True,
            )
        print("=== ISOLATED WORKER SUBPROCESS TIMINGS ===", flush=True)
        worker_groups = defaultdict(lambda: [0, 0.0])
        for module, duration in self.workers:
            group = worker_groups[module]
            group[0] += 1
            group[1] += duration
        for module, (count, total) in sorted(
            worker_groups.items(), key=lambda row: row[1][1], reverse=True
        ):
            print(
                f"SECONDARY_WORKER module={module} count={count} "
                f"total_seconds={total:.3f}",
                flush=True,
            )
        print(
            f"SECONDARY_WORKER_COUNT={len(self.workers)} "
            f"TOTAL_SECONDS={sum(row[1] for row in self.workers):.3f}",
            flush=True,
        )
        if self.import_sample:
            print("=== SAMPLED CHILD IMPORT COST (MICROSECONDS) ===", flush=True)
            for worker, rows in sorted(self.import_samples.items()):
                print(
                    f"SECONDARY_IMPORT_SAMPLE module={worker} "
                    f"records={len(rows)}",
                    flush=True,
                )
                for imported, self_us, cumulative_us in sorted(
                    rows, key=lambda row: row[2], reverse=True
                )[:12]:
                    print(
                        f"SECONDARY_IMPORT worker={worker} "
                        f"imported={imported} self_us={self_us} "
                        f"cumulative_us={cumulative_us}",
                        flush=True,
                    )


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--test", choices=sorted(TARGETS), default="workflow"
    )
    parser.add_argument(
        "--import-sample", action="store_true",
        help=(
            "Capture CPython import times for the first private worker "
            "of each module. Slows sampled calls; diagnostic only."
        ),
    )
    args = parser.parse_args(argv)

    if socket.gethostname().split(".")[0] != "tracker-dev":
        parser.error("diagnostic profiling is allowed only on tracker-dev")

    if ROOT.resolve() == Path("/opt/tracker").resolve():
        parser.error("run in a disposable candidate worktree, not /opt/tracker")

    if not (ROOT / "tests/conftest.py").is_file():
        parser.error("cannot find isolated pytest fixtures")

    os.chdir(ROOT)
    sys.path.insert(0, str(ROOT))

    # Importing pytest and httpx does not import Tracker application config.
    # The test conftest must run before any app imports to enforce test data
    # isolation. Do not import app.* before pytest.main().
    import pytest

    recorder = TimingRecorder(import_sample=args.import_sample)
    recorder.install()
    try:
        code = pytest.main([
            "-q", "-s", "--tb=short", "--maxfail=1",
            "--durations=8", TARGETS[args.test],
        ])
    finally:
        recorder.uninstall()
        recorder.report()

    print(f"SECONDARY_PROFILE_TEST_EXIT={int(code)}", flush=True)
    return int(code)


if __name__ == "__main__":
    sys.exit(main())
