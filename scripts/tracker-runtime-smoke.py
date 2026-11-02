#!/usr/bin/env python3
"""Authenticated, read-only live HTTP smoke of Tracker sidebar destinations."""
import argparse
import base64
from html.parser import HTMLParser
from pathlib import Path
import re
import shlex
import subprocess
import time
import urllib.error
import urllib.request


class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.in_sidebar = False
        self.paths = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "nav" and attrs.get("id") == "app-sidebar":
            self.in_sidebar = True
        if self.in_sidebar and tag == "a":
            url = attrs.get("href", "")
            if url.startswith("/") and not url.startswith("//"):
                self.paths.append(url.split("?", 1)[0])

    def handle_endtag(self, tag):
        if tag == "nav" and self.in_sidebar:
            self.in_sidebar = False


def read_env(path):
    settings = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].strip()
        if "=" not in line:
            continue
        name, raw = line.split("=", 1)
        name = name.strip()
        if name in ("TRACKER_INSTANCE", "TRACKER_USER", "TRACKER_PASS"):
            fields = shlex.split(raw.strip(), comments=False)
            if len(fields) != 1:
                raise ValueError(f"Invalid {name} in local environment")
            settings[name] = fields[0]
    return settings


def port_from_service():
    result = subprocess.run(
        ["systemctl", "show", "tracker", "-p", "ExecStart", "--value"],
        text=True, capture_output=True, check=True,
    )
    match = re.search(r"--port(?:\s+|=)(\d+)", result.stdout)
    return int(match.group(1)) if match else 8000


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def run(instance, envfile):
    settings = read_env(envfile)
    if settings.get("TRACKER_INSTANCE", "").upper() != instance:
        raise ValueError("Instance mismatch")
    headers = {"User-Agent": "Tracker-Release-Smoke/1.0"}
    if settings.get("TRACKER_USER") and settings.get("TRACKER_PASS"):
        token = (settings["TRACKER_USER"] + ":" + settings["TRACKER_PASS"]).encode()
        headers["Authorization"] = "Basic " + base64.b64encode(token).decode()
    opener = urllib.request.build_opener(
        urllib.request.ProxyHandler({}), NoRedirect()
    )
    origin = f"http://127.0.0.1:{port_from_service()}"

    def get(path, startup=False):
        deadline = time.monotonic() + (30 if startup else 0)
        while True:
            status = 0
            try:
                request = urllib.request.Request(origin + path, headers=headers)
                with opener.open(request, timeout=6) as result:
                    status = result.status
                    body = result.read(3 * 1024 * 1024)
                if status == 200:
                    return body
            except urllib.error.HTTPError as error:
                status = error.code
            except OSError:
                pass
            if time.monotonic() >= deadline:
                raise ValueError(f"{path}: HTTP {status}")
            time.sleep(1)

    health = get("/healthz", startup=True)
    if b'"ok":true' not in health.replace(b" ", b""):
        raise ValueError("Health check content invalid")
    dashboard = get("/")
    parser = Links()
    parser.feed(dashboard.decode("utf-8", errors="replace"))
    paths = list(dict.fromkeys(parser.paths))
    if len(paths) < 35:
        raise ValueError(f"Sidebar unexpectedly contains {len(paths)} paths")
    failures = []
    for path in paths:
        try:
            body = dashboard if path == "/" else get(path)
            if b"<title>" not in body or (
                f"tracker-instance--{instance.lower()}".encode() not in body
            ):
                failures.append(f"{path}: missing title/instance badge")
        except (OSError, ValueError) as error:
            failures.append(f"{path}: {str(error)[:120]}")
    if failures:
        raise ValueError(
            f"{len(failures)}/{len(paths)} pages failed: "
            + "; ".join(failures[:12])
        )
    print(f"PASS: /healthz and {len(paths)} sidebar pages HTTP 200; {instance} identity")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--instance", choices=("DEV", "PROD"), required=True)
    parser.add_argument("--envfile", type=Path, default=Path("/etc/tracker.env"))
    args = parser.parse_args()
    try:
        run(args.instance, args.envfile)
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        print(f"FAIL: Live HTTP smoke: {str(error)[:1200]}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
