#!/usr/bin/env python3
"""Authenticated, read-only live HTTP smoke of Tracker sidebar destinations."""
import argparse
import base64
import json
import os
import sys
from contextlib import contextmanager
from html.parser import HTMLParser
from pathlib import Path
import re
import shlex
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request


def validate_sidebar_path(path):
    """Reject malformed escapes and control bytes in local URLs."""
    if any(ord(char) < 32 or ord(char) == 127 for char in path):
        raise ValueError(
            "Sidebar URL contains control characters"
        )

    if re.search(r"%(?![0-9A-Fa-f]{2})", path):
        raise ValueError(
            "Sidebar URL has malformed percent encoding"
        )

    decoded = urllib.parse.unquote_to_bytes(path)

    if any(byte < 32 or byte == 127 for byte in decoded):
        raise ValueError(
            "Sidebar URL contains encoded control characters"
        )



class Links(HTMLParser):
    """Collect sidebar links without losing nested navigation."""

    def __init__(self):
        super().__init__()
        self.sidebar_depth = 0
        self.sidebar_containers = 0
        self.paths = []

    def handle_starttag(self, tag, attrs):
        # HTML permits duplicate attribute syntax, but silently
        # selecting one value makes sidebar discovery ambiguous.
        if tag == "nav":
            ids = [
                value for name, value in attrs
                if name == "id"
            ]
            if len(ids) > 1 and (
                self.sidebar_depth
                or "app-sidebar" in ids
            ):
                raise ValueError(
                    "Ambiguous sidebar navigation id attributes"
                )

        if tag == "a" and self.sidebar_depth:
            hrefs = [
                value for name, value in attrs
                if name == "href"
            ]
            if len(hrefs) > 1:
                raise ValueError(
                    "Ambiguous sidebar link href attributes"
                )

        attrs = dict(attrs)

        if tag == "nav":
            if attrs.get("id") == "app-sidebar":
                self.sidebar_containers += 1

            if self.sidebar_depth:
                self.sidebar_depth += 1
            elif attrs.get("id") == "app-sidebar":
                self.sidebar_depth = 1

        if self.sidebar_depth and tag == "a":
            url = attrs.get("href") or ""

            # Reject control characters before URL parsing can
            # silently normalize them away.
            if url.startswith("/") and not url.startswith("//"):
                if any(
                    ord(char) < 32 or ord(char) == 127
                    for char in url
                ):
                    raise ValueError(
                        "Sidebar URL contains control characters"
                    )

            # Only local absolute paths represent sidebar pages.
            # Fragments and queries do not identify distinct pages.
            if not url.startswith("/") or url.startswith("//"):
                return

            try:
                parsed = urllib.parse.urlsplit(url)
            except ValueError:
                return

            if (
                not parsed.scheme
                and not parsed.netloc
                and parsed.path.startswith("/")
                and not parsed.path.startswith("//")
            ):
                validate_sidebar_path(parsed.path)
                self.paths.append(parsed.path)

    def handle_endtag(self, tag):
        if tag == "nav" and self.sidebar_depth:
            self.sidebar_depth -= 1


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
        if name in (
            "TRACKER_INSTANCE",
            "TRACKER_USER",
            "TRACKER_PASS",
            "TRACKER_DATA_DIR",
        ):
            fields = shlex.split(raw.strip(), comments=False)
            if len(fields) != 1:
                raise ValueError(f"Invalid {name} in local environment")
            settings[name] = fields[0]
    return settings


def port_from_service():
    """Require one valid, unambiguous configured TCP port."""
    result = subprocess.run(
        ["systemctl", "show", "tracker", "-p", "ExecStart", "--value"],
        text=True, capture_output=True, check=True,
    )

    declarations = re.findall(
        r"(?<!\S)--port(?=\s|=|;|$)",
        result.stdout,
    )

    matches = re.findall(
        r"(?<!\S)--port(?:\s+|=)(\d+)(?=\s|;|$)",
        result.stdout,
    )

    match = re.search(
        r"(?<!\S)--port(?:\s+|=)(\d+)(?=\s|;|$)",
        result.stdout,
    )

    # Preserve Release 550's missing/malformed-port contract.
    if match is None:
        raise ValueError(
            "Tracker systemd ExecStart has no valid --port"
        )

    # Release 551: even identical duplicate declarations are unsafe.
    if len(declarations) != 1 or len(matches) != 1:
        raise ValueError(
            "Tracker systemd ExecStart must specify exactly "
            "one valid --port"
        )

    port = int(match.group(1))

    if not 1 <= port <= 65535:
        raise ValueError(
            "Tracker systemd ExecStart port out of range"
        )

    return port


def service_working_directory():
    """Resolve relative data paths against systemd's working directory."""
    result = subprocess.run(
        ["systemctl", "show", "tracker",
         "-p", "WorkingDirectory", "--value"],
        text=True,
        capture_output=True,
        check=True,
    )

    value = result.stdout.strip()

    if not value:
        raise ValueError(
            "Tracker systemd WorkingDirectory is unset"
        )

    directory = Path(value)

    if not directory.is_absolute():
        raise ValueError(
            "Tracker systemd WorkingDirectory is not absolute"
        )

    directory = directory.resolve()

    if not directory.is_dir():
        raise ValueError(
            "Tracker systemd WorkingDirectory does not exist"
        )

    return directory


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None



@contextmanager
def _release_auth_headers_unmanaged(instance, settings):
    """Use a revocable session for local DEV and PROD verification.

    The release process invokes this script as root. No HTTP
    authentication bypass is installed in the application.
    """
    headers = {
        "User-Agent": "Tracker-Release-Smoke/1.0",
    }

    if instance in ("DEV", "PROD"):
        raw_directory = (
            settings.get("TRACKER_DATA_DIR")
            or str(Path(__file__).resolve().parents[1] / "data")
        )

        directory = Path(raw_directory).expanduser()

        if not directory.is_absolute():
            directory = (
                service_working_directory() / directory
            )

        directory = directory.resolve()

        flag = directory / ".tracker-session-auth-dev"

        if flag.is_file():
            # Load the application from the installed source.
            root = str(Path(__file__).resolve().parents[1])
            if root not in sys.path:
                sys.path.insert(0, root)

            os.environ["TRACKER_INSTANCE"] = instance
            os.environ["TRACKER_DATA_DIR"] = str(directory)

            from app import session_auth385 as auth

            if not auth.enabled():
                raise ValueError(
                    "Session auth is configured but unavailable"
                )

            token, _ = auth.create_session(False)

            # Allow a bounded ten-minute diagnostic window, including
            # readiness and sidebar checks. Always revoke on exit.
            import hashlib

            hashed = hashlib.sha256(
                token.encode()
            ).hexdigest()

            with auth.connect() as db:
                db.execute("""
                    UPDATE sessions
                    SET expires_at=?
                    WHERE token_hash=? AND user_id=1
                """, (int(time.time()) + 600, hashed))

            headers["Cookie"] = (
                auth.COOKIE + "=" + token
            )

            try:
                yield headers
            finally:
                auth.revoke(token)

            return

    # Preserve Basic Auth only where session mode is disabled.
    if (
        settings.get("TRACKER_USER")
        and settings.get("TRACKER_PASS")
    ):
        token = (
            settings["TRACKER_USER"]
            + ":"
            + settings["TRACKER_PASS"]
        ).encode()

        headers["Authorization"] = (
            "Basic "
            + base64.b64encode(token).decode()
        )

    yield headers


@contextmanager
def release_auth_headers(instance, settings):
    """Restore diagnostic environment after success or failure."""
    names = ("TRACKER_INSTANCE", "TRACKER_DATA_DIR")
    previous = {name: os.environ.get(name) for name in names}

    try:
        with _release_auth_headers_unmanaged(
            instance, settings
        ) as headers:
            yield headers
    finally:
        for name, value in previous.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value




class SmokeRequestError(ValueError):
    """HTTP failure or transport failure without leaking credentials."""


class SmokeAuthenticationRedirect(SmokeRequestError):
    """An authenticated request was redirected to login."""


class SmokeAuthenticationRejected(SmokeRequestError):
    """An authenticated request was explicitly rejected."""


MAX_RESPONSE_BYTES = 3 * 1024 * 1024


def fetch_page(opener, origin, path, headers, timeout=6):
    """Return complete page bytes or preserve the failure category."""
    request = urllib.request.Request(
        origin + path, headers=headers,
    )
    try:
        with opener.open(request, timeout=timeout) as response:
            status = response.status
            body = response.read(MAX_RESPONSE_BYTES + 1)
    except urllib.error.HTTPError as error:
        status = error.code
        destination = error.headers.get("Location", "")
        error.close()

        # Never include response bodies, request credentials,
        # or authorization headers in diagnostic messages.
        if status in (401, 403):
            raise SmokeAuthenticationRejected(
                f"AUTH_REJECTED HTTP {status}"
            ) from None

        # Never display redirect query parameters, which may
        # contain user-supplied URLs or other sensitive values.
        redirect_path = urllib.parse.urlsplit(
            destination
        ).path

        if status in (301, 302, 303, 307, 308) and (
            redirect_path == "/login"
        ):
            raise SmokeAuthenticationRedirect(
                f"AUTH_REDIRECT HTTP {status} to /login"
            ) from None

        raise SmokeRequestError(
            f"HTTP {status}"
        ) from None
    except urllib.error.URLError as error:
        # Exception messages can include credentials, URLs,
        # or internal hostnames. Report only the error type.
        reason = error.reason
        category = (
            type(reason).__name__
            if isinstance(reason, BaseException)
            else "URLError"
        )
        raise SmokeRequestError(
            "TRANSPORT " + category
        ) from None
    except (OSError, TimeoutError) as error:
        raise SmokeRequestError(
            "TRANSPORT " + type(error).__name__
        ) from None

    if status != 200:
        raise SmokeRequestError(f"HTTP {status}")

    if len(body) > MAX_RESPONSE_BYTES:
        raise SmokeRequestError(
            "HTTP 200 with response exceeding size limit"
        )

    return body


def validate_health_response(body):
    """Require a top-level JSON health status of boolean true."""
    try:
        payload = json.loads(body)
    except (ValueError, UnicodeDecodeError):
        raise SmokeRequestError(
            "HTTP 200 with invalid health JSON"
        ) from None

    if not isinstance(payload, dict) or payload.get("ok") is not True:
        raise SmokeRequestError(
            "HTTP 200 with invalid health status"
        )


def wait_for_authenticated_readiness(opener, origin, headers):
    """Require both health and authenticated dashboard before traversal."""
    deadline = time.monotonic() + 45
    last_failure = "not attempted"
    attempts = 0

    while True:
        attempts += 1
        try:
            health = fetch_page(
                opener, origin, "/healthz", headers,
            )
            validate_health_response(health)

            dashboard = fetch_page(
                opener, origin, "/", headers,
            )
            if b"<title>" not in dashboard:
                raise SmokeRequestError(
                    "HTTP 200 with invalid dashboard content"
                )

            print(
                f"READINESS=PASS attempts={attempts}",
                flush=True,
            )
            return dashboard

        except (
            SmokeAuthenticationRedirect,
            SmokeAuthenticationRejected,
        ) as error:
            raise ValueError(
                "Authenticated readiness rejected: "
                + str(error)
            ) from None
        except SmokeRequestError as error:
            last_failure = str(error)

        if time.monotonic() >= deadline:
            raise ValueError(
                "Authenticated readiness failed after "
                f"{attempts} attempts: {last_failure}"
            )

        time.sleep(1)




def validate_sidebar_structure(parser):
    """Require exactly one complete sidebar navigation container."""
    if parser.sidebar_containers != 1:
        raise ValueError(
            "Expected exactly one app-sidebar navigation container: "
            f"found {parser.sidebar_containers}"
        )

    if parser.sidebar_depth != 0:
        raise ValueError(
            "Sidebar navigation container is not closed"
        )

    print("SIDEBAR_STRUCTURE=PASS containers=1", flush=True)


MIN_SIDEBAR_ENDPOINTS = 52


def validate_sidebar_coverage(paths):
    """Reject incomplete sidebar discovery before HTTP traversal."""
    unique_count = len(set(paths))

    if unique_count < MIN_SIDEBAR_ENDPOINTS:
        raise ValueError(
            "Sidebar coverage below required minimum: "
            f"{unique_count}/{MIN_SIDEBAR_ENDPOINTS} "
            "unique destinations"
        )

    print(
        f"SIDEBAR_COVERAGE=PASS "
        f"unique={unique_count} "
        f"minimum={MIN_SIDEBAR_ENDPOINTS}",
        flush=True,
    )




def validate_dashboard_identity(dashboard, instance):
    """Require the expected instance badge before sidebar traversal."""
    if instance not in ("DEV", "PROD"):
        raise ValueError("Invalid smoke instance")

    badge = (
        f"tracker-instance--{instance.lower()}"
    ).encode()

    if b"<title>" not in dashboard or badge not in dashboard:
        raise SmokeRequestError(
            "HTTP 200 with missing dashboard title/instance badge"
        )

    print(
        f"DASHBOARD_IDENTITY=PASS instance={instance}",
        flush=True,
    )



def run(instance, envfile):
    settings = read_env(envfile)

    if settings.get("TRACKER_INSTANCE", "").upper() != instance:
        raise ValueError("Instance mismatch")

    with release_auth_headers(instance, settings) as headers:
        opener = urllib.request.build_opener(
            urllib.request.ProxyHandler({}), NoRedirect()
        )
        origin = f"http://127.0.0.1:{port_from_service()}"

        dashboard = wait_for_authenticated_readiness(
            opener, origin, headers
        )

        validate_dashboard_identity(dashboard, instance)

        parser = Links()
        parser.feed(
            dashboard.decode("utf-8", errors="replace")
        )
        parser.close()

        validate_sidebar_structure(parser)

        paths = list(dict.fromkeys(parser.paths))

        validate_sidebar_coverage(paths)

        failures = []
        started = time.monotonic()

        print(f"SIDEBAR_ENDPOINTS={len(paths)}", flush=True)

        for number, path in enumerate(paths, 1):
            before = time.monotonic()

            try:
                body = (
                    dashboard if path == "/"
                    else fetch_page(
                        opener, origin, path, headers
                    )
                )

                if (
                    b"<title>" not in body
                    or (
                        f"tracker-instance--{instance.lower()}"
                    ).encode() not in body
                ):
                    raise SmokeRequestError(
                        "HTTP 200 with missing title/instance badge"
                    )

                elapsed = time.monotonic() - before

                print(
                    f"{number:02d}/{len(paths):02d} "
                    f"PASS {path}: HTTP 200 ({elapsed:.2f}s)",
                    flush=True,
                )

            except (
                SmokeAuthenticationRedirect,
                SmokeAuthenticationRejected,
            ) as error:
                raise ValueError(
                    "Authenticated sidebar rejected: "
                    + str(error)
                ) from None
            except SmokeRequestError as error:
                elapsed = time.monotonic() - before
                reason = str(error)

                failures.append((path, reason))

                print(
                    f"{number:02d}/{len(paths):02d} "
                    f"FAIL {path}: {reason} ({elapsed:.2f}s)",
                    flush=True,
                )

        duration = time.monotonic() - started

        print(f"SIDEBAR_FAILURES={len(failures)}")
        print(f"SIDEBAR_ELAPSED_SECONDS={duration:.1f}")

        if failures:
            details = "; ".join(
                f"{path}: {reason}"
                for path, reason in failures[:12]
            )
            raise ValueError(
                f"{len(failures)}/{len(paths)} pages failed: "
                + details
            )

        print(
            f"PASS: /healthz and {len(paths)} sidebar pages "
            f"HTTP 200; {instance} identity"
        )


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
