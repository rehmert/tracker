/* Release 656: permission-on-tap camera QR reader; no external QR requests.
   BarcodeDetector is a progressive enhancement; the manual lookup always works. */
(() => {
  "use strict";
  const root = document.getElementById("workout-qr-camera656");
  if (!root) return;

  const start = root.querySelector("[data-start656]");
  const stopButton = root.querySelector("[data-stop656]");
  const preview = root.querySelector("[data-preview656]");
  const video = root.querySelector("video");
  const status = root.querySelector("[data-status656]");
  let stream = null;
  let running = false;
  let inFlight = false;
  let detector = null;
  let generation = 0;

  const setStatus = (message) => {
    status.textContent = message;
  };

  const shutdown = () => {
    generation++;
    running = false;
    if (stream) {
      for (const track of stream.getTracks()) track.stop();
      stream = null;
    }
    video.pause();
    video.srcObject = null;
    preview.hidden = true;
    stopButton.hidden = true;
    start.hidden = false;
  };

  async function scanFrame() {
    if (!running || document.visibilityState === "hidden") return;
    if (!inFlight && video.readyState >= 2) {
      inFlight = true;
      try {
        const codes = await detector.detect(video);
        if (!running) return;
        const raw = codes.length ? String(codes[0].rawValue || "").trim() : "";
        if (raw) {
          if (raw.length > 1024) {
            setStatus("This QR code is too long for a machine mapping.");
          } else {
            shutdown();
            setStatus("QR code found. Looking up the machine…");
            // Only the current origin is used. Never open the QR destination.
            window.location.assign("/workouts/qr?code=" + encodeURIComponent(raw));
            return;
          }
        }
      } catch (_) {
        // The camera may be warming up. Let the user stop or retry.
        if (running) setStatus("Scanner could not read this frame. Try again or paste the code.");
      } finally {
        inFlight = false;
      }
    }
    if (running) window.requestAnimationFrame(scanFrame);
  }

  setStatus("Manual QR entry works on all supported browsers.");
  if (!window.isSecureContext ||
      !("BarcodeDetector" in window) ||
      !navigator.mediaDevices ||
      !navigator.mediaDevices.getUserMedia) {
    setStatus("Camera QR scanning is unavailable in this browser. Paste the QR text or URL instead.");
    return;
  }
  try {
    detector = new window.BarcodeDetector({ formats: ["qr_code"] });
  } catch (_) {
    setStatus("QR detection is unavailable in this browser. Use manual QR entry.");
    return;
  }

  start.hidden = false;
  start.addEventListener("click", async () => {
    if (running || stream) return;
    start.disabled = true;
    const attempt = ++generation;
    setStatus("Requesting camera access…");
    try {
      const acquired = await navigator.mediaDevices.getUserMedia({
        audio: false, video: { facingMode: { ideal: "environment" } },
      });
      // Permission may resolve after tab hide, Stop, or navigation.
      if (attempt !== generation || document.visibilityState === "hidden") {
        for (const track of acquired.getTracks()) track.stop();
        return;
      }
      stream = acquired;
      video.srcObject = stream;
      preview.hidden = false;
      stopButton.hidden = false;
      start.hidden = true;
      running = true;
      await video.play();
      if (attempt !== generation || !running) return;
      setStatus("Point your camera at a machine QR code.");
      window.requestAnimationFrame(scanFrame);
    } catch (_) {
      if (attempt === generation) {
        shutdown();
        setStatus("Unable to start camera. Check camera permission, or paste the QR code.");
      }
    } finally {
      start.disabled = false;
    }
  });
  stopButton.addEventListener("click", () => {
    shutdown();
    setStatus("Camera stopped. You can still paste a QR code.");
  });
  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "hidden") shutdown();
  });
  window.addEventListener("pagehide", shutdown);
})();
