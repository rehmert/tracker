/* Release 656: DOM-mocked camera scanner tests; no real camera or network. */
"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");

const source = fs.readFileSync(
  "app/static/js/tracker-workouts656.js", "utf8"
);

function button(initiallyHidden = true) {
  const events = new Map();
  return {
    hidden: initiallyHidden, disabled: false, textContent: "",
    addEventListener(type, fn) { events.set(type, fn); },
    fire(type) { return events.get(type)?.(); },
  };
}

function fixture(options = {}) {
  const start = button();
  const stop = button();
  const preview = { hidden: true };
  const status = { textContent: "" };
  const video = {
    readyState: 2, srcObject: null,
    pause() {}, async play() {},
  };
  const lookup = new Map([
    ["[data-start656]", start],
    ["[data-stop656]", stop],
    ["[data-preview656]", preview],
    ["[data-status656]", status],
    ["video", video],
  ]);
  const root = { querySelector: (name) => lookup.get(name) };
  const docEvents = new Map();
  const pageEvents = new Map();
  const frames = [];
  let redirects = [];
  let stopped = 0;
  const stream = {
    getTracks() { return [{ stop() { stopped++; } }]; },
  };
  const document = {
    visibilityState: "visible",
    getElementById(name) { return name === "workout-qr-camera656" ? root : null; },
    addEventListener(name, fn) { docEvents.set(name, fn); },
  };
  const window = {
    isSecureContext: options.secure !== false,
    location: { assign(path) { redirects.push(path); } },
    requestAnimationFrame(fn) { frames.push(fn); },
    addEventListener(name, fn) { pageEvents.set(name, fn); },
  };
  if (options.supported !== false) {
    window.BarcodeDetector = class {
      constructor(opts) { assert.deepEqual(Array.from(opts.formats), ["qr_code"]); }
      async detect() {
        return options.detect ? options.detect() : [];
      }
    };
  }
  const navigator = {
    mediaDevices: {
      async getUserMedia(opts) {
        assert.equal(opts.audio, false);
        assert.equal(opts.video.facingMode.ideal, "environment");
        if (options.denied) throw Error("Permission denied");
        if (options.acquire) return options.acquire();
        return stream;
      },
    },
  };

  vm.runInNewContext(source, {
    window, document, navigator, encodeURIComponent, console,
  }, { timeout: 1000 });

  return {
    start, stop, preview, status, video, frames, window, document,
    docEvents, pageEvents,
    get redirects() { return redirects; },
    get stopped() { return stopped; },
  };
}

async function main() {
  const unavailable = fixture({ supported: false });
  assert.equal(unavailable.start.hidden, true);
  assert.match(unavailable.status.textContent, /unavailable/i);

  const insecure = fixture({ secure: false });
  assert.equal(insecure.start.hidden, true);

  const url = "https://example.invalid/nautilus?unit=1&tag=%26";
  const supported = fixture({
    detect: () => [{ rawValue: url }],
  });
  assert.equal(supported.start.hidden, false);
  await supported.start.fire("click");
  assert.equal(supported.preview.hidden, false);
  assert.equal(supported.start.hidden, true);
  assert.equal(supported.frames.length, 1);
  await supported.frames.shift()();
  assert.deepEqual(supported.redirects, [
    "/workouts/qr?code=" + encodeURIComponent(url),
  ]);
  assert.equal(supported.stopped, 1);
  assert.equal(supported.preview.hidden, true);

  const denied = fixture({ denied: true });
  await denied.start.fire("click");
  assert.match(denied.status.textContent, /Unable to start camera/);
  assert.equal(denied.start.disabled, false);
  assert.equal(denied.preview.hidden, true);

  const stop = fixture();
  await stop.start.fire("click");
  stop.stop.fire("click");
  assert.equal(stop.stopped, 1);
  assert.deepEqual(stop.redirects, []);
  assert.equal(stop.preview.hidden, true);

  const pagehide = fixture();
  await pagehide.start.fire("click");
  pagehide.pageEvents.get("pagehide")();
  assert.equal(pagehide.stopped, 1);

  const hidden = fixture();
  await hidden.start.fire("click");
  hidden.document.visibilityState = "hidden";
  hidden.docEvents.get("visibilitychange")();
  assert.equal(hidden.stopped, 1);

  let resolveCamera;
  let lateStops = 0;
  const late = fixture({
    acquire: () => new Promise((resolve) => { resolveCamera = resolve; }),
  });
  const pending = late.start.fire("click");
  late.pageEvents.get("pagehide")();
  resolveCamera({
    getTracks() { return [{ stop() { lateStops++; } }]; },
  });
  await pending;
  assert.equal(lateStops, 1);
  assert.equal(late.preview.hidden, true);
  assert.equal(late.frames.length, 0);
  assert.deepEqual(late.redirects, []);

  const tooLong = fixture({
    detect: () => [{ rawValue: "X".repeat(1025) }],
  });
  await tooLong.start.fire("click");
  await tooLong.frames.shift()();
  assert.deepEqual(tooLong.redirects, []);
  assert.match(tooLong.status.textContent, /too long/i);
  tooLong.stop.fire("click");

  console.log("WORKOUT_656_CAMERA_DOM_TESTS=PASSED");
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
