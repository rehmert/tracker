/* Release 666: read-only Rapid Gym view of Release 665 browser-local intentions.
   Never fills logging inputs, writes storage, or submits workout data. */
(() => {
  "use strict";
  const panel = document.getElementById("workout666-targets");
  if (!panel) return;
  const routineId = panel.dataset.routineId666 || "";
  const itemId = panel.dataset.itemId666 || "";
  if (!/^[1-9]\d*$/.test(routineId) || !/^[1-9]\d*$/.test(itemId)) return;

  // The same versioned per-routine key and item IDs as the Release 665 planner.
  const key = "tracker.workout665.plan.routine." + routineId;
  const status = document.getElementById("workout666-targets-status");
  const list = document.getElementById("workout666-target-values");
  if (!status || !list) return;
  const rules = {
    sets: { min: 1, max: 20, integer: true, suffix: "" },
    reps: { min: 1, max: 200, integer: true, suffix: "" },
    weight: { min: 0, max: 2000, integer: false, suffix: " lb" }
  };

  function display(value) {
    list.hidden = true;
    status.textContent = value;
    for (const kind of Object.keys(rules)) {
      const node = list.querySelector('[data-target666="' + kind + '"]');
      if (node) node.textContent = "—";
    }
  }

  function safeNumber(kind, value) {
    if (typeof value !== "string" || !value || value.length > 32) return null;
    const number = Number(value);
    const rule = rules[kind];
    if (!Number.isFinite(number) || number < rule.min || number > rule.max ||
        (rule.integer && !Number.isInteger(number))) return null;
    return String(number) + rule.suffix;
  }

  function refresh() {
    let raw;
    try {
      raw = window.localStorage.getItem(key);
    } catch (_) {
      display("Browser targets are unavailable. Open the routine planner to view them.");
      return;
    }
    if (!raw) {
      display("No saved targets for this machine on this browser.");
      return;
    }
    let payload;
    try {
      payload = JSON.parse(raw);
    } catch (_) {
      display("No valid saved targets for this machine on this browser.");
      return;
    }
    if (!payload || typeof payload !== "object" || Array.isArray(payload) ||
        payload.version !== 1 || !payload.targets ||
        typeof payload.targets !== "object" || Array.isArray(payload.targets)) {
      display("No valid saved targets for this machine on this browser.");
      return;
    }
    const plan = payload.targets[itemId];
    if (!plan || typeof plan !== "object" || Array.isArray(plan)) {
      display("No saved targets for this machine on this browser.");
      return;
    }
    let count = 0;
    for (const kind of Object.keys(rules)) {
      const node = list.querySelector('[data-target666="' + kind + '"]');
      if (!node) continue;
      const result = safeNumber(kind, plan[kind]);
      node.textContent = result === null ? "—" : result;
      if (result !== null) count++;
    }
    if (count) {
      status.textContent = "Saved on this browser; targets are not logged.";
      list.hidden = false;
    } else {
      display("No valid saved targets for this machine on this browser.");
    }
  }

  // Returning from the planner (including bfcache) and changes in other tabs.
  window.addEventListener("pageshow", refresh);
  window.addEventListener("storage", event => {
    if (event.key === key || event.key === null) refresh();
  });
  refresh();
})();
