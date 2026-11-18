#!/usr/bin/env python3
"""Capture authenticated DEV pages for *manual* visual review only.

Read-only navigation. Session state and screenshots remain on the DEV host.
Never publish screenshots containing personal records in GitHub/CI artifacts.
"""
import argparse
import os
from pathlib import Path
from urllib.parse import urlparse

from playwright.sync_api import sync_playwright

PAGES = {
    "overview": "/",
    "today": "/mobile",
    "food": "/food",
    "doses": "/doses",
    "workouts": "/workouts",
    "gym": "/workouts/quick",
}
VIEWPORTS = {"phone": (390, 844), "desktop": (1280, 900)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", required=True, help="Full DEV origin, e.g. https://tracker-dev.example")
    parser.add_argument("--storage-state", required=True, type=Path,
                        help="Playwright authenticated state JSON, stored privately on DEV")
    parser.add_argument("--output-dir", required=True, type=Path,
                        help="Private output directory on DEV; no automatic upload")
    parser.add_argument("--pages", nargs="+", choices=sorted(PAGES), default=["overview", "today", "food", "doses", "workouts", "gym"])
    args = parser.parse_args()

    parsed = urlparse(args.base_url)
    if parsed.scheme != "https" or not parsed.netloc or parsed.username or parsed.password or parsed.path not in ("", "/"):
        parser.error("--base-url must be a bare HTTPS DEV origin without credentials or path")
    if "dev" not in parsed.hostname.lower():
        parser.error("--base-url must identify DEV; never capture PROD")
    if not args.storage_state.is_file() or args.storage_state.is_symlink():
        parser.error("Private authenticated storage-state file is required")
    state_mode = args.storage_state.stat().st_mode & 0o777
    if state_mode & 0o077:
        parser.error("Storage-state file must be private (chmod 600)")

    args.output_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    if args.output_dir.is_symlink() or (args.output_dir.stat().st_mode & 0o077):
        parser.error("Output directory must be private (chmod 700)")
    base = args.base_url.rstrip("/")
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            headless=True,
            executable_path=os.environ.get("TRACKER_TEST_CHROMIUM_PATH") or None,
        )
        try:
            for name in args.pages:
                for view, (width, height) in VIEWPORTS.items():
                    context = browser.new_context(
                        storage_state=str(args.storage_state),
                        viewport={"width": width, "height": height},
                        device_scale_factor=1,
                        color_scheme="dark" if view == "desktop" else "light",
                    )
                    page = context.new_page()
                    expected = base + PAGES[name]
                    try:
                        response = page.goto(expected, wait_until="domcontentloaded", timeout=20000)
                        if response is None or response.status >= 400:
                            raise RuntimeError(f"{name} {view}: non-success response")
                        page.locator("#main-content").wait_for(state="visible", timeout=10000)
                        if not urlparse(page.url).path.startswith(PAGES[name]):
                            raise RuntimeError(f"{name} {view}: unexpected redirect (possible login)")
                        # Avoid accidental captures of pages not authenticated to the app.
                        if page.locator('input[type="password"]').count():
                            raise RuntimeError(f"{name} {view}: login form detected")
                        # Fixed deterministic viewport; snapshots are review material, not baselines.
                        page.screenshot(path=str(args.output_dir / f"{name}-{view}.png"),
                                        full_page=True, animations="disabled")
                        overflow = page.evaluate(
                            "() => document.documentElement.scrollWidth > innerWidth + 1"
                        )
                        print(f"VISUAL679_CAPTURE={name}:{view}:OK;HORIZONTAL_OVERFLOW={int(overflow)}")
                    finally:
                        context.close()
        finally:
            browser.close()
    print("VISUAL679_REVIEW=REQUIRED_MANUAL_NO_AUTOMATIC_APPROVAL")


if __name__ == "__main__":
    main()
