"""Release 668: real Chromium offline queue, replay and phone-width regressions."""
import json
from pathlib import Path
from uuid import uuid4

import pytest
from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parents[2]
OFFLINE = (ROOT / "app/static/js/tracker-workout-offline668.js").read_text(encoding="utf-8")
CSS = (ROOT / "app/static/css/tracker-workout-advanced668.css").read_text(encoding="utf-8")
URL = "https://tracker.test/workouts/quick?machine=50"


def page668():
    return f"""<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>*{{box-sizing:border-box}}body{{margin:0;padding:10px}}{CSS}</style>
</head><body>
<section id="workout659-root" data-session-id="17" data-last-set-id=""
 data-logged="no">
  <form id="workout659-log-form" action="/workouts/quick/sets" method="post">
    <input name="equipment_id" type="hidden" value="50">
    <label>Weight<input name="weight_lb" type="number" value="95" min="0" max="2000" required></label>
    <label>Reps<input name="reps" type="number" value="10" min="1" max="200" required></label>
    <input name="effort" value="7" type="number">
    <label><input name="set_type" type="radio" value="working" checked>Working</label>
    <label><input name="set_type" type="radio" value="warmup">Warm-up</label>
    <button id="workout659-save" type="submit">Save Set</button>
  </form>
  <aside class="workout668-offline">
    <button id="workout668-queue-set" type="button">Queue Set Offline</button>
    <button id="workout668-sync-set" type="button">Sync Queued Sets</button>
    <p id="workout668-offline-status" role="status" aria-live="polite"></p>
  </aside>
</section>
<script>{OFFLINE}</script></body></html>"""


@pytest.mark.browser
@pytest.mark.parametrize("width,height", [(320,740),(390,844),(393,852)])
def test_668_mobile_explicit_offline_queue_and_single_ack(width, height):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={"width":width,"height":height},
            is_mobile=True, has_touch=True, device_scale_factor=3,
        )
        page = context.new_page()
        errors, replay = [], []
        page.on("pageerror", lambda error: errors.append(str(error)))
        def intercept(route):
            replay.append(route.request.post_data)
            route.fulfill(
                status=200, content_type="application/json",
                body='{"ok":true,"duplicate":false,"set_id":73}',
            )
        context.route("**/workouts/offline/sync", intercept)
        context.route("**/workouts/quick*", lambda route: route.fulfill(
            status=200, content_type="text/html; charset=utf-8", body=page668()
        ))
        try:
            page.goto(URL)
            assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
            expect(page.locator("#workout668-offline-status")).to_contain_text("0 set(s) pending")
            page.get_by_role("button", name="Queue Set Offline").click()
            expect(page.locator("#workout668-offline-status")).to_contain_text("1 set(s) pending")
            queue = page.evaluate(
                "() => JSON.parse(localStorage.getItem('tracker.workout668.offline.17'))"
            )
            assert len(queue) == 1
            assert queue[0]["weight_lb"] == "95"
            assert queue[0]["reps"] == "10"
            assert queue[0]["set_type"] == "working"
            assert len(replay) == 0
            assert page.locator("#workout659-save").is_enabled()
            page.get_by_role("button", name="Sync Queued Sets").click()
            expect(page.locator("#workout668-offline-status")).to_contain_text("0 set(s) pending")
            assert len(replay) == 1
            page.get_by_role("button", name="Sync Queued Sets").click()
            assert len(replay) == 1
            assert not errors, errors
        finally:
            context.close()
            browser.close()


@pytest.mark.browser
def test_668_queue_survives_failed_sync_and_can_retry():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={"width":390,"height":844}, is_mobile=True, has_touch=True
        )
        page = context.new_page()
        calls = []
        context.route("**/workouts/offline/sync", lambda route: (
            calls.append(route.request.method),
            route.fulfill(
                status=409, content_type="application/json",
                body='{"ok":false,"error":"session mismatch"}',
            )
        ))
        context.route("**/workouts/quick*", lambda route: route.fulfill(
            status=200, content_type="text/html; charset=utf-8", body=page668()
        ))
        try:
            page.goto(URL)
            page.get_by_role("button", name="Queue Set Offline").click()
            page.get_by_role("button", name="Sync Queued Sets").click()
            expect(page.locator("#workout668-offline-status")).to_contain_text("1 set(s) pending")
            assert calls == ["POST"]
            assert len(page.evaluate(
                "() => JSON.parse(localStorage.getItem('tracker.workout668.offline.17'))"
            )) == 1
        finally:
            context.close()
            browser.close()
