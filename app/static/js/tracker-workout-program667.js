/* Release 667: explicit browser-local plan import; no automatic migration. */
(() => {
  "use strict";
  const root = document.getElementById("workout667-program");
  const form = document.getElementById("workout667-import-form");
  const status = document.getElementById("workout667-import-status");
  const payload = document.getElementById("workout667-import-payload");
  if (!root || !form || !status || !payload) return;
  const id = root.dataset.routineId667 || "";
  if (!/^[1-9]\d*$/.test(id)) return;
  const key = "tracker.workout665.plan.routine." + id;
  form.addEventListener("submit", event => {
    event.preventDefault();
    let parsed;
    try {
      parsed = JSON.parse(localStorage.getItem(key) || "null");
    } catch (_) {
      status.textContent = "Browser targets unavailable or invalid.";
      return;
    }
    if (!parsed || parsed.version !== 1 || !parsed.targets ||
        typeof parsed.targets !== "object" || Array.isArray(parsed.targets) ||
        !Object.keys(parsed.targets).length) {
      status.textContent = "No browser targets available to import.";
      return;
    }
    // Exact server validation includes ownership, target ranges and completeness.
    const serialized = JSON.stringify(parsed);
    if (serialized.length > 16000) {
      status.textContent = "Browser target data is too large.";
      return;
    }
    payload.value = serialized;
    status.textContent = "Submitting targets for server validation…";
    form.submit();
  });
})();
