#!/usr/bin/env python3
"""Release 704: read-only latency baseline against disposable local app only.

Only HTTP GET to a strict 127.0.0.1 URL. No credentials, redirects,
external hosts, user identifiers, writes, installation or stored metrics.
"""
import argparse
import statistics
import time
import urllib.error
import urllib.parse
import urllib.request

PAGES = (
    "/", "/mobile", "/food", "/doses", "/vitals", "/workouts/quick",
    "/vials", "/purchases", "/coas", "/labs",
)


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError(f"Redirect prohibited for latency baseline: {code}")


def run(base):
    url = urllib.parse.urlsplit(base)
    if not (url.scheme == "http" and url.hostname == "127.0.0.1"
            and url.port is not None and not url.username and not url.password
            and url.path in ("", "/") and not url.query and not url.fragment):
        raise ValueError("Only explicit http://127.0.0.1:PORT accepted")
    opener = urllib.request.build_opener(
        urllib.request.ProxyHandler({}), NoRedirect()
    )
    result = {}
    for path in PAGES:
        samples = []
        for _ in range(3):
            request = urllib.request.Request(
                base.rstrip("/") + path,
                method="GET",
                headers={"Accept": "text/html"},
            )
            start = time.perf_counter()
            with opener.open(request, timeout=8) as response:
                if response.status != 200:
                    raise ValueError(f"Unexpected status {response.status}")
                data = response.read(2 * 1024 * 1024)
                if not data:
                    raise ValueError("Empty route response")
            samples.append(round((time.perf_counter() - start) * 1000, 1))
        result[path] = round(statistics.median(samples), 1)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", required=True)
    args = parser.parse_args()
    values = run(args.url)
    for path, median in values.items():
        print(f"LATENCY704_{path}={median}ms")
    print("RELEASE_704_READ_ONLY_PERFORMANCE=COLLECTED")
    print("RELEASE_704_PERFORMANCE_NOTE=BASELINE_ONLY_NO_OPTIMIZATION_CLAIM")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
