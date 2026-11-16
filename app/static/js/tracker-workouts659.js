/* Release 659 rapid gym floor mode: browser-only controls and rest countdown.
   The server owns every workout mutation; no timer events write to Tracker. */
(() => {
  "use strict";
  const root = document.getElementById("workout659-root");
  if (!root) return;

  const logForm = document.getElementById("workout659-log-form");
  const saveButton = document.getElementById("workout659-save");
  const controls = root.querySelectorAll("[data-step659]");

  for (const control of controls) {
    control.addEventListener("click", () => {
      if (!logForm) return;
      const kind = control.dataset.step659;
      const input = logForm.querySelector(
        kind === "weight" ? 'input[name="weight_lb"]' : 'input[name="reps"]'
      );
      if (!input) return;
      const delta = Number(control.dataset.delta659);
      const fallback = kind === "weight" ? 0 : 1;
      const current = input.value.trim() === "" ? fallback : Number(input.value);
      if (!Number.isFinite(current) || !Number.isFinite(delta)) return;
      const minimum = kind === "weight" ? 0 : 1;
      const maximum = kind === "weight" ? 2000 : 200;
      const value = Math.max(minimum, Math.min(maximum, current + delta));
      input.value = kind === "weight" ? String(Math.round(value * 10) / 10) : String(value);
      input.dispatchEvent(new Event("input", { bubbles: true }));
      input.focus();
    });
  }

  if (logForm && saveButton) {
    logForm.addEventListener("submit", (event) => {
      if (event.defaultPrevented) return;
      if (logForm.dataset.submitting659 === "1") {
        event.preventDefault();
        return;
      }
      logForm.dataset.submitting659 = "1";
      saveButton.disabled = true;
      saveButton.textContent = "Saving…";
    });
  }
  // Repeat uses the server's source-set-ID stale guard; disable duplicate taps.
  const repeat = root.querySelector(".workout659-repeat");
  if (repeat) {
    repeat.addEventListener("submit", (event) => {
      if (event.defaultPrevented) return;
      if (repeat.dataset.submitting659 === "1") {
        event.preventDefault();
        return;
      }
      repeat.dataset.submitting659 = "1";
      const button = repeat.querySelector('button[type="submit"]');
      if (button) button.disabled = true;
    });
  }

  const sessionId = root.dataset.sessionId || "";
  const display = document.getElementById("workout659-rest-display");
  const status = document.getElementById("workout659-rest-status");
  const durationSelect = document.getElementById("workout659-rest-duration");
  const startButton = document.getElementById("workout659-rest-start");
  const resetButton = document.getElementById("workout659-rest-reset");
  if (!sessionId || !display || !status || !durationSelect || !startButton || !resetButton) {
    return;
  }

  const prefix = "tracker-workout659:" + sessionId + ":";
  const secondsKey = "tracker-workout659:rest-seconds";
  let deadline = null;
  let expired = false;
  const safeGet = (key) => {
    try { return window.sessionStorage.getItem(key); } catch (_) { return null; }
  };
  const safeSet = (key, value) => {
    try { window.sessionStorage.setItem(key, String(value)); } catch (_) { /* optional */ }
  };
  const safeRemove = (key) => {
    try { window.sessionStorage.removeItem(key); } catch (_) { /* optional */ }
  };
  const savedSeconds = Number(safeGet(secondsKey));
  if ([60, 90, 120, 180].includes(savedSeconds)) {
    durationSelect.value = String(savedSeconds);
  }
  const chosenSeconds = () => Number(durationSelect.value) || 90;
  function format(seconds) {
    const s = Math.max(0, Math.ceil(seconds));
    return String(Math.floor(s / 60)).padStart(2, "0") + ":" +
      String(s % 60).padStart(2, "0");
  }
  function render() {
    if (deadline === null) {
      display.textContent = format(chosenSeconds());
      status.textContent = expired ? "Rest interval completed." :
        "Ready. Save a set or start the timer manually.";
      return;
    }
    const remaining = Math.max(0, (deadline - Date.now()) / 1000);
    display.textContent = format(remaining);
    if (remaining === 0) {
      deadline = null;
      expired = true;
      safeRemove(prefix + "deadline");
      status.textContent = "Rest interval completed.";
      return;
    }
    status.textContent = "Resting — countdown continues when changing machines.";
  }
  function startTimer() {
    deadline = Date.now() + chosenSeconds() * 1000;
    expired = false;
    safeSet(prefix + "deadline", deadline);
    render();
  }
  function resetTimer() {
    deadline = null;
    expired = false;
    safeRemove(prefix + "deadline");
    render();
  }
  const restored = Number(safeGet(prefix + "deadline"));
  if (Number.isFinite(restored) && restored > 0 && restored > Date.now()) {
    deadline = restored;
  } else if (Number.isFinite(restored) && restored > 0 && restored <= Date.now()) {
    expired = true;
    safeRemove(prefix + "deadline");
  }

  durationSelect.addEventListener("change", () => {
    safeSet(secondsKey, chosenSeconds());
    if (deadline === null) render();
  });
  startButton.addEventListener("click", startTimer);
  resetButton.addEventListener("click", resetTimer);

  // Successful POST redirects back to the same machine with logged=1.
  // Tie automatic start to the committed set ID: reload never restarts rest.
  const lastId = root.dataset.lastSetId || "";
  if (root.dataset.logged === "yes" && lastId) {
    if (safeGet(prefix + "seen-set") !== lastId) {
      safeSet(prefix + "seen-set", lastId);
      startTimer();
    }
  }
  render();
  window.setInterval(render, 250);
})();
