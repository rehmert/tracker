/*
 * Release 461: optional browser-native barcode scanner.
 *
 * Camera images are processed locally by BarcodeDetector.
 * Only the recognized barcode goes to the existing lookup.
 * There are no image uploads and no automatic food saves.
 */
(function () {
  "use strict";

  const startButton = document.getElementById(
    "barcode-scan461"
  );
  const stopButton = document.getElementById(
    "barcode-stop461"
  );
  const video = document.getElementById(
    "barcode-video461"
  );
  const status = document.getElementById(
    "barcode-camera-status461"
  );
  const barcode = document.getElementById(
    "barcode-code460"
  );
  const lookup = document.getElementById(
    "barcode-lookup460"
  );

  if (
    !startButton || !stopButton || !video ||
    !status || !barcode || !lookup
  ) {
    return;
  }

  const supported =
    window.isSecureContext &&
    typeof window.BarcodeDetector === "function" &&
    navigator.mediaDevices &&
    typeof navigator.mediaDevices.getUserMedia === "function";

  if (!supported) {
    startButton.hidden = true;
    status.textContent =
      "Camera scanning is unavailable in this browser. " +
      "Enter the barcode manually.";
    return;
  }

  const formats = [
    "ean_13",
    "ean_8",
    "upc_a",
    "upc_e",
    "code_128",
    "itf"
  ];

  let stream = null;
  let detector = null;
  let active = false;
  let generation = 0;
  let frameHandle = 0;
  let lastAttempt = 0;
  let scanBusy = false;

  function stopCamera(message) {
    generation += 1;
    active = false;

    if (frameHandle) {
      cancelAnimationFrame(frameHandle);
      frameHandle = 0;
    }

    if (stream) {
      stream.getTracks().forEach(function (track) {
        track.stop();
      });
      stream = null;
    }

    video.pause();
    video.srcObject = null;
    video.hidden = true;

    stopButton.hidden = true;
    startButton.hidden = false;
    startButton.disabled = false;

    if (typeof message === "string") {
      status.textContent = message;
    }
  }

  async function scanFrame(now, ticket) {
    if (!active || ticket !== generation) {
      return;
    }

    if (
      !scanBusy &&
      now - lastAttempt >= 180 &&
      video.readyState >= 2
    ) {
      lastAttempt = now;
      scanBusy = true;

      try {
        const results = await detector.detect(video);

        if (!active || ticket !== generation) {
          return;
        }

        for (const result of results) {
          const value = String(
            result.rawValue || ""
          ).trim();

          if (/^[0-9]{8,14}$/.test(value)) {
            barcode.value = value;

            stopCamera(
              "Barcode detected. Looking up nutrition..."
            );

            // Existing GET-only lookup fills editable fields.
            // It does not submit the food journal form.
            lookup.click();
            return;
          }
        }
      } catch (_error) {
        // A transient frame decoding failure should not
        // terminate the entire camera session.
      } finally {
        scanBusy = false;
      }
    }

    if (active && ticket === generation) {
      frameHandle = requestAnimationFrame(
        function (timestamp) {
          void scanFrame(timestamp, ticket);
        }
      );
    }
  }

  async function startCamera() {
    stopCamera();
    const ticket = generation;

    startButton.disabled = true;
    stopButton.hidden = false;
    status.textContent = "Requesting camera access...";

    try {
      let available = formats;

      if (
        typeof window.BarcodeDetector
          .getSupportedFormats === "function"
      ) {
        const browserFormats =
          await window.BarcodeDetector.getSupportedFormats();

        if (ticket !== generation) {
          return;
        }

        available = formats.filter(function (format) {
          return browserFormats.includes(format);
        });

        if (available.length === 0) {
          throw new Error("No supported barcode formats");
        }
      }

      detector = new window.BarcodeDetector({
        formats: available
      });

      const acquired =
        await navigator.mediaDevices.getUserMedia({
          audio: false,
          video: {
            facingMode: { ideal: "environment" },
            width: { ideal: 1280 },
            height: { ideal: 720 }
          }
        });

      if (ticket !== generation) {
        acquired.getTracks().forEach(function (track) {
          track.stop();
        });
        return;
      }

      stream = acquired;
      video.srcObject = stream;
      video.hidden = false;

      await video.play();

      if (ticket !== generation) {
        stopCamera();
        return;
      }

      active = true;
      lastAttempt = 0;
      scanBusy = false;

      startButton.hidden = true;
      startButton.disabled = false;
      stopButton.hidden = false;

      status.textContent =
        "Point the camera at a product barcode. " +
        "Press Stop Camera to cancel.";

      frameHandle = requestAnimationFrame(
        function (timestamp) {
          void scanFrame(timestamp, ticket);
        }
      );
    } catch (_error) {
      if (ticket === generation) {
        stopCamera(
          "Camera access or barcode detection is unavailable. " +
          "Enter the barcode manually."
        );
      }
    }
  }

  startButton.addEventListener("click", function () {
    void startCamera();
  });

  stopButton.addEventListener("click", function () {
    stopCamera("Camera stopped.");
  });

  document.addEventListener("visibilitychange", function () {
    if (document.hidden) {
      stopCamera("Camera stopped when page was hidden.");
    }
  });

  window.addEventListener("pagehide", function () {
    stopCamera();
  });
})();
