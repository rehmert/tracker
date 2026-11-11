#!/usr/bin/env python3
"""Replay the observed Tracker dependency baseline in a disposable DEV sandbox.

Plan-only by default. --execute downloads pinned wheels and Chromium to a
private temporary directory; never modifies /opt/tracker/.venv, live databases,
service settings, or GitHub. Requires an explicit DEV root invocation.
"""
from __future__ import annotations

import argparse
import hashlib
import os
from pathlib import Path
import shutil
import signal
import socket
import subprocess
import sys
import tempfile

APP = Path("/opt/tracker")
EXPECTED_SCRIPT = APP / "scripts/tracker_freshenv570.py"
MIN_FREE_BYTES = 1024**3
PYPI = "https://pypi.org/simple"


class ReplayError(RuntimeError):
    pass


def call(args: list[str], *, cwd=None, env=None, timeout=1200) -> None:
    """Stream output, preserve exit failures, terminate an entire timed-out group."""
    print(f"SUBPROCESS={Path(args[0]).name} arguments={len(args) - 1}", flush=True)
    process = subprocess.Popen(
        args, cwd=cwd, env=env, start_new_session=True,
    )
    try:
        status = process.wait(timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        os.killpg(process.pid, signal.SIGTERM)
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait()
        raise ReplayError("Command timed out; isolated subprocess group stopped") from exc
    if status != 0:
        raise ReplayError(f"Isolated command failed with exit code {status}")


def git(*args: str) -> str:
    return subprocess.check_output(
        ["git", "-c", f"safe.directory={APP}", "-C", str(APP), *args],
        text=True,
    ).strip()


def preflight() -> str:
    if os.geteuid() != 0 or socket.gethostname().split(".", 1)[0] != "tracker-dev":
        raise ReplayError("Run as root on tracker-dev only")
    if Path(__file__).resolve() != EXPECTED_SCRIPT:
        raise ReplayError("Use the installed DEV copy of the freshenv script")
    if git("branch", "--show-current") != "main" or git("status", "--porcelain"):
        raise ReplayError("Installed DEV checkout must be clean main")
    if not Path("/opt/tracker/.venv/bin/python").is_file():
        raise ReplayError("Known DEV Python environment is missing")
    if shutil.disk_usage("/tmp").free < MIN_FREE_BYTES:
        raise ReplayError("Under 1 GiB free in /tmp: insufficient sandbox capacity")
    for name in (
        "docs/dependencies/observed-2026-11-11-py313.json",
        "docs/dependencies/candidate-constraints-py313.txt",
        "scripts/tracker-browser-qualify.sh",
        "scripts/tracker-test.sh",
    ):
        if not (APP / name).is_file():
            raise ReplayError(f"Required tracked source unavailable: {name}")
    print(f"DEV_SOURCE_COMMIT={git('rev-parse', 'HEAD')}", flush=True)
    print("LIVE_TRACKER_MUTATIONS=NONE", flush=True)
    print("DOWNLOAD_SOURCE=PYPI_AND_PLAYWRIGHT_CDN", flush=True)
    print("REPLAY_PREFLIGHT=PASSED", flush=True)
    return git("rev-parse", "HEAD")


def env_for_sandbox(home: Path, source: Path, data: Path) -> dict[str, str]:
    return {
        "HOME": str(home),
        "PATH": "/usr/local/bin:/usr/bin:/bin",
        "LANG": "C.UTF-8",
        "PYTHONNOUSERSITE": "1",
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONUNBUFFERED": "1",
        "PYTHONPATH": str(source),
        "TRACKER_DATA_DIR": str(data),
        "TRACKER_INSTANCE": "DEV",
    }


def wheel_receipt(wheels: Path) -> int:
    items = sorted(wheels.glob("*.whl"))
    if len(items) < 44:
        raise ReplayError("Wheelhouse contains fewer than the 44 observed packages")
    report = wheels.parent / "wheel-sha256.txt"
    lines = []
    for path in items:
        if path.is_symlink() or not path.is_file():
            raise ReplayError("Unsafe wheelhouse entry")
        with path.open("rb") as stream:
            digest = hashlib.file_digest(stream, "sha256").hexdigest()
        lines.append(f"{digest}  {path.name}")
    report.write_text("\n".join(lines) + "\n", encoding="utf-8")
    report.chmod(0o600)
    print(f"WHEELHOUSE_WHEELS={len(items)}")
    print(f"WHEEL_SHA256_RECEIPT={report}")
    return len(items)


def temporary_browser_runner(source: Path, home: Path, destination: Path) -> None:
    """Only a TEMPORARY copy overrides hard-coded HOME=/root in QA subprocesses.

    The tracked browser qualification code and installed /opt/tracker remain
    byte-for-byte unchanged. Browser processes use the newly downloaded
    Chromium at <private-home>/.cache/ms-playwright, not root's cache.
    """
    original = (source / "scripts/tracker-browser-qualify.sh").read_text(
        encoding="utf-8"
    )
    marker = "HOME=/root"
    if original.count(marker) < 4:
        raise ReplayError("Browser QA isolation contract changed; refuse to patch")
    if "env -i" not in original or "ISOLATED_STRICT_CSRF_BROWSER=PASSED" not in original:
        raise ReplayError("Unsupported browser qualification source")
    if any(char.isspace() for char in str(home)):
        raise ReplayError("Invalid browser sandbox path")
    # Controlled replacement of HOME in a single disposable COPY.
    rewritten = original.replace(marker, f"HOME={home}")
    destination.write_text(rewritten, encoding="utf-8")
    destination.chmod(0o700)
    print("BROWSER_QA_HOME_OVERRIDE=TEMP_COPY_ONLY", flush=True)


def execute(source_sha: str, *, retain: bool) -> None:
    runroot = Path(tempfile.mkdtemp(prefix="tracker-freshenv570-", dir="/tmp"))
    runroot.chmod(0o700)
    source = runroot / "source"
    venv = runroot / "venv"
    home = runroot / "home"
    data = runroot / "data"
    wheels = runroot / "wheelhouse"
    for path in (home, data, wheels):
        path.mkdir(mode=0o700)
    environment = env_for_sandbox(home, source, data)
    worktree_added = False
    try:
        print(f"ISOLATED_ROOT={runroot}", flush=True)
        print("[1/7] Creating detached source worktree", flush=True)
        call(["git", "-c", f"safe.directory={APP}", "-C", str(APP),
              "worktree", "add", "--detach", str(source), source_sha], timeout=90)
        worktree_added = True
        if subprocess.check_output(
            ["git", "-C", str(source), "rev-parse", "HEAD"], text=True,
        ).strip() != source_sha:
            raise ReplayError("Detached worktree commit mismatch")

        print("[2/7] Creating fresh Python 3.13 virtual environment", flush=True)
        base_python = "/opt/tracker/.venv/bin/python"
        call([base_python, "-m", "venv", str(venv)], timeout=120)
        python = str(venv / "bin/python")
        settings = (venv / "pyvenv.cfg").read_text(encoding="utf-8").lower()
        if "include-system-site-packages = false" not in settings:
            raise ReplayError("New venv unexpectedly accesses system site-packages")
        constraints = str(source / "docs/dependencies/candidate-constraints-py313.txt")

        print("[3/7] Downloading pinned wheels from PyPI to a private wheelhouse",
              flush=True)
        call([python, "-m", "pip", "--isolated", "download",
              "--disable-pip-version-check", "--only-binary=:all:",
              "--index-url", PYPI, "--dest", str(wheels),
              "-r", constraints, "pip==25.1.1"], env=environment, timeout=1200)
        wheel_receipt(wheels)

        print("[4/7] Reinstalling all pinned packages OFFLINE", flush=True)
        call([python, "-m", "pip", "--isolated", "install",
              "--disable-pip-version-check", "--no-index",
              "--no-input", "--only-binary=:all:", "--find-links", str(wheels),
              "-r", constraints, "pip==25.1.1"], env=environment, timeout=600)
        call([python, str(source / "scripts/tracker_dependency_baseline569.py"),
              "--instance", "DEV",
              "--baseline", str(source / "docs/dependencies/observed-2026-11-11-py313.json"),
              "--constraints", constraints], env=environment, timeout=90)
        print("FRESHENV_PACKAGE_BASELINE=PASSED", flush=True)

        print("[5/7] Downloading and launching separate Chromium", flush=True)
        call([python, "-m", "playwright", "install", "chromium"],
             env=environment, timeout=900)
        # A real Chromium process with a data: page, not a reused binary.
        smoke = (
            "from playwright.sync_api import sync_playwright\n"
            "with sync_playwright() as p:\n"
            " b=p.chromium.launch(headless=True)\n"
            " try:\n"
            "  page=b.new_page()\n"
            "  page.goto('data:text/html,<title>Tracker sandbox</title>')\n"
            "  assert page.title()=='Tracker sandbox'\n"
            " finally:\n"
            "  b.close()\n"
        )
        call([python, "-c", smoke], env=environment, timeout=120)
        print("FRESHENV_CHROMIUM_LAUNCH=PASSED", flush=True)

        print("[6/7] Full backend suite with fresh virtual environment",
              flush=True)
        backend_env = dict(environment)
        backend_env["TRACKER_TEST_PYTHON"] = python
        backend_env["TRACKER_TEST_WORKERS"] = "8"
        call(["bash", str(source / "scripts/tracker-test.sh"), "--parallel-check"],
             cwd=source, env=backend_env, timeout=1500)
        print("FRESHENV_BACKEND_SUITE=PASSED", flush=True)

        print("[7/7] Existing isolated browser QA using fresh Chromium", flush=True)
        browser = runroot / "browser-qa-temp.sh"
        temporary_browser_runner(source, home, browser)
        call(["bash", str(browser), str(source), python],
             cwd=source, env=environment, timeout=1200)
        print("FRESHENV_BROWSER_SUITE=PASSED", flush=True)
    finally:
        worktree_cleanup_ok = True
        if worktree_added:
            try:
                call(["git", "-c", f"safe.directory={APP}", "-C", str(APP),
                      "worktree", "remove", "--force", str(source)], timeout=90)
            except ReplayError:
                worktree_cleanup_ok = False
                print("ERROR: Detached worktree cleanup failed", file=sys.stderr)
        if retain:
            print(f"ISOLATED_ARTIFACTS_RETAINED={runroot}", flush=True)
            print("Artifacts are under /tmp, not a durable backup", flush=True)
        else:
            shutil.rmtree(runroot)
            print("ISOLATED_ARTIFACTS_REMOVED=YES", flush=True)
        if not worktree_cleanup_ok:
            raise ReplayError("Detached worktree cleanup must be investigated")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true",
                        help="Actually download and test in a disposable sandbox")
    parser.add_argument("--retain-artifacts", action="store_true",
                        help="Keep private /tmp wheel receipts and browser files")
    args = parser.parse_args(argv)
    if args.retain_artifacts and not args.execute:
        parser.error("--retain-artifacts requires --execute")
    try:
        sha = preflight()
        if not args.execute:
            print("DRY_RUN=PASSED; --execute required to download/test")
            return 0
        execute(sha, retain=args.retain_artifacts)
        print("FRESHENV_REPLAY=SUCCESS", flush=True)
        return 0
    except (ReplayError, OSError, UnicodeError, subprocess.CalledProcessError) as exc:
        print(f"FRESHENV_REPLAY=FAILED ({type(exc).__name__}: {exc})",
              file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
