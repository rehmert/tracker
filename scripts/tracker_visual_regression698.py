#!/usr/bin/env python3
"""Release 698: compare real, disposable Tracker pages to pinned release baseline.

No authentication state, live data, external URL, GitHub uploads, record writes,
or dependency downloads. Both app origins MUST be loopback with distinct ports.
Screenshots are viewport-sized. On mismatch, private artifacts remain on DEV.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from urllib.parse import urlsplit
import os
import re
import sys

from PIL import Image, ImageChops
from playwright.sync_api import sync_playwright

PAGES = {
    "overview": "/",
    "today": "/mobile",
    "food": "/food",
    "doses": "/doses",
    "vitals": "/vitals",
    "gym": "/workouts/quick",
    "vials": "/vials",
    "purchases": "/purchases",
    "coas": "/coas",
    "labs": "/labs",
}
# A focused second screenshot catches lower-page layouts on longer screens.
ANCHORS = {
    "food": "#food-quick-log",
    "doses": "#dose-history",
    "vitals": "#quick-vitals-entry",
    "vials": "#tracker-vials-sortable",
    "purchases": "#new-purchase",
    "coas": "#tracker-flow696-coa-table",
    "labs": "#labs-reports-section",
}
VIEWPORTS = {
    "small-phone": (320, 844),
    "phone": (390, 844),
    "tablet": (768, 900),
    "desktop": (1280, 900),
}
THEMES = ("light", "dark")
MAX_CHANGED = 0.012
PIXEL_DIFFERENCE = 28

STABLE_STYLE = """
*, *::before, *::after {
  animation: none !important;
  transition: none !important;
  caret-color: transparent !important;
}
"""


@dataclass(frozen=True)
class Difference:
    changed: int
    total: int
    fraction: float
    width: int
    height: int


def require_loopback(url: str) -> str:
    parsed = urlsplit(url)
    if (parsed.scheme != "http" or parsed.hostname != "127.0.0.1"
            or not parsed.port or parsed.username or parsed.password
            or parsed.path not in ("", "/") or parsed.query or parsed.fragment):
        raise ValueError("Both origins must be bare http://127.0.0.1:<port> URLs")
    return url.rstrip("/")


def difference_png(base_png: bytes, candidate_png: bytes) -> Difference:
    with Image.open(BytesIO(base_png)) as a, Image.open(BytesIO(candidate_png)) as b:
        reference = a.convert("RGB")
        current = b.convert("RGB")
    if reference.size != current.size:
        raise ValueError(f"Screenshot dimensions differ: {reference.size} != {current.size}")
    # C-backed Pillow operations; no NumPy or extra dependencies.
    gray = ImageChops.difference(reference, current).convert("L")
    histogram = gray.histogram()
    changed = sum(histogram[PIXEL_DIFFERENCE:])
    total = reference.width * reference.height
    return Difference(changed, total, changed / total, reference.width, reference.height)


def save_failure(folder: Path, label: str, a: bytes, b: bytes) -> None:
    folder.mkdir(mode=0o700, parents=True, exist_ok=True)
    folder.chmod(0o700)
    if not re.fullmatch(r"[a-z0-9-]+", label):
        raise ValueError("Invalid artifact label")
    (folder / (label + "-baseline.png")).write_bytes(a)
    (folder / (label + "-candidate.png")).write_bytes(b)
    with Image.open(BytesIO(a)) as first, Image.open(BytesIO(b)) as second:
        ImageChops.difference(first.convert("RGB"), second.convert("RGB")).save(
            folder / (label + "-diff.png")
        )
    for file in folder.glob(label + "-*.png"):
        file.chmod(0o600)


def capture(page, url: str, name: str) -> tuple[bytes, dict]:
    response = page.goto(url + PAGES[name], wait_until="networkidle", timeout=30000)
    if not response or response.status != 200:
        raise AssertionError(f"{name}: expected HTTP 200, got {response.status if response else 'no response'}")
    page.locator("#main-content").wait_for(state="visible", timeout=10000)
    if urlsplit(page.url).path.rstrip("/") != PAGES[name].rstrip("/"):
        raise AssertionError(f"{name}: unexpected redirect")
    if page.locator('input[type="password"]').count():
        raise AssertionError(f"{name}: login form detected")
    page.add_style_tag(content=STABLE_STYLE)
    page.evaluate("window.scrollTo(0, 0)")
    page.evaluate("() => document.fonts.ready")
    metrics = page.evaluate("""() => ({
      theme: document.documentElement.dataset.theme,
      overflow: Math.max(0, document.documentElement.scrollWidth - innerWidth),
      heading: document.querySelector('#main-content h1')?.textContent?.trim() || '',
      main: document.querySelector('#main-content')?.getBoundingClientRect().width || 0
    })""")
    return page.screenshot(animations="disabled", caret="hide"), metrics


def capture_anchor(page, selector: str) -> bytes | None:
    target = page.locator(selector)
    if target.count() != 1:
        return None
    target.scroll_into_view_if_needed()
    page.evaluate("() => document.fonts.ready")
    return page.screenshot(animations="disabled", caret="hide")


def visual_run(baseline_url: str, candidate_url: str, artifact_dir: Path) -> tuple[int, int]:
    baseline_url = require_loopback(baseline_url)
    candidate_url = require_loopback(candidate_url)
    if baseline_url == candidate_url:
        raise ValueError("Baseline and candidate must have different loopback ports")
    if not artifact_dir.is_absolute() or artifact_dir.is_symlink():
        raise ValueError("Private artifact path must be absolute and not a symlink")

    comparisons = 0
    failures = 0
    allowed_ports = {urlsplit(baseline_url).port, urlsplit(candidate_url).port}

    def isolated_request(route):
        # Fail closed on external assets, trackers and unintended localhost
        # services; only our two isolated loopback servers may receive traffic.
        parsed = urlsplit(route.request.url)
        try:
            allowed = (
                parsed.scheme == "http"
                and parsed.hostname == "127.0.0.1"
                and parsed.port in allowed_ports
            )
        except ValueError:
            allowed = False
        if allowed:
            route.continue_()
        else:
            route.abort()

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            headless=True,
            executable_path=os.environ.get("TRACKER_TEST_CHROMIUM_PATH") or None,
        )
        try:
            for view, (width, height) in VIEWPORTS.items():
                for theme in THEMES:
                    context = browser.new_context(
                        viewport={"width": width, "height": height},
                        device_scale_factor=1,
                        color_scheme=theme,
                        reduced_motion="reduce",
                        locale="en-US",
                        timezone_id="America/New_York",
                    )
                    context.route("**/*", isolated_request)
                    # Every origin receives the same preference before its theme
                    # script executes; separate page/session state by context.
                    context.add_init_script(
                        "(function(){try{localStorage.setItem('tracker-theme',"
                        + repr(theme) + ");}catch(_){}})();"
                    )
                    reference = context.new_page()
                    candidate = context.new_page()
                    try:
                        for name in PAGES:
                            label = f"{name}-{view}-{theme}"
                            a, metrics_a = capture(reference, baseline_url, name)
                            b, metrics_b = capture(candidate, candidate_url, name)
                            if metrics_a["theme"] != theme or metrics_b["theme"] != theme:
                                raise AssertionError(f"{label}: theme preference did not apply")
                            if metrics_a["heading"] != metrics_b["heading"]:
                                raise AssertionError(f"{label}: page heading changed")
                            if metrics_b["overflow"] > metrics_a["overflow"] + 1:
                                raise AssertionError(f"{label}: horizontal overflow increased")
                            if abs(metrics_b["main"] - metrics_a["main"]) > 2:
                                raise AssertionError(f"{label}: main content width changed")
                            checks = [("top", a, b)]
                            if name in ANCHORS:
                                more_a = capture_anchor(reference, ANCHORS[name])
                                more_b = capture_anchor(candidate, ANCHORS[name])
                                if (more_a is None) != (more_b is None):
                                    raise AssertionError(f"{label}: anchored section disappeared")
                                if more_a is not None and more_b is not None:
                                    checks.append(("detail", more_a, more_b))
                            for section, old, new in checks:
                                key = f"{label}-{section}"
                                diff = difference_png(old, new)
                                comparisons += 1
                                if diff.fraction > MAX_CHANGED:
                                    failures += 1
                                    save_failure(artifact_dir, key, old, new)
                                    print(
                                        f"VISUAL698_DIFF_FAILURE={key}:"
                                        f"changed={diff.fraction:.4%}:"
                                        f"limit={MAX_CHANGED:.2%}",
                                        flush=True,
                                    )
                                else:
                                    print(f"VISUAL698_PASS={key}:{diff.fraction:.4%}", flush=True)
                    finally:
                        context.close()
        finally:
            browser.close()
    return comparisons, failures


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline-url", required=True)
    parser.add_argument("--candidate-url", required=True)
    parser.add_argument("--artifact-dir", type=Path, required=True)
    args = parser.parse_args()

    if os.environ.get("TRACKER_TEST_ISOLATED") != "1":
        parser.error("TRACKER_TEST_ISOLATED=1 is required")
    try:
        checks, failures = visual_run(
            args.baseline_url, args.candidate_url, args.artifact_dir
        )
    except (ValueError, AssertionError) as error:
        print(f"VISUAL698_ERROR={error}", file=sys.stderr)
        return 1
    print(f"VISUAL698_COMPARISONS={checks}")
    print(f"VISUAL698_FAILURES={failures}")
    minimum = len(PAGES) * len(VIEWPORTS) * len(THEMES)
    if checks < minimum:
        print(f"VISUAL698_ERROR=Only {checks} of {minimum} required comparisons executed", file=sys.stderr)
        return 1
    if failures:
        print(f"VISUAL698_REVIEW_ARTIFACTS={args.artifact_dir}")
        return 1
    print("VISUAL698_BASELINE_COMPARISON=PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
