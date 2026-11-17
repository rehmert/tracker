/* Release 665: optional user-entered plan drafts, stored on this browser only.
   The server supplies read-only actual performance. No fetch/POST or set logging. */
(() => {
  "use strict";
  const root = document.getElementById("workout665-planner");
  if (!root) return;
  const routineId = root.dataset.routineId665 || "";
  if (!/^[1-9]\d*$/.test(routineId)) return;
  const key = "tracker.workout665.plan.routine." + routineId;
  const rows = Array.from(root.querySelectorAll(
    ".workout665-exercise[data-item-id665]"
  ));
  const status = document.getElementById("workout665-save-status");
  const clear = document.getElementById("workout665-clear-all");
  const kinds = ["sets", "reps", "weight"];
  const rules = {
    sets: { min: 1, max: 20, integer: true },
    reps: { min: 1, max: 200, integer: true },
    weight: { min: 0, max: 2000, integer: false }
  };
  const show = message => { if (status) status.textContent = message; };

  function safeRead() {
    try {
      const raw = window.localStorage.getItem(key);
      if (!raw) return {};
      const value = JSON.parse(raw);
      if (!value || typeof value !== "object" || Array.isArray(value) ||
          value.version !== 1 || !value.targets ||
          typeof value.targets !== "object" || Array.isArray(value.targets)) return {};
      return value.targets;
    } catch (_) {
      return {};
    }
  }

  function valid(kind, value) {
    if (typeof value !== "string" || value === "") return false;
    const number = Number(value);
    const rule = rules[kind];
    return Number.isFinite(number) && number >= rule.min && number <= rule.max &&
      (!rule.integer || Number.isInteger(number));
  }

  for (const row of rows) {
    const id = row.dataset.itemId665;
    const saved = safeRead()[id];
    if (!saved || typeof saved !== "object" || Array.isArray(saved)) continue;
    for (const kind of kinds) {
      const input = row.querySelector('[data-field665="' + kind + '"]');
      const value = saved[kind];
      if (input && valid(kind, value)) input.value = value;
    }
  }

  function persist() {
    const targets = {};
    for (const row of rows) {
      const values = {};
      for (const kind of kinds) {
        const input = row.querySelector('[data-field665="' + kind + '"]');
        if (!input) continue;
        const value = input.value.trim();
        if (value && !valid(kind, value)) {
          show("Invalid target. Please use the displayed ranges; nothing was saved.");
          return;
        }
        if (value) values[kind] = value;
      }
      if (Object.keys(values).length) targets[row.dataset.itemId665] = values;
    }
    try {
      if (Object.keys(targets).length) {
        window.localStorage.setItem(key, JSON.stringify({
          version: 1, targets: targets
        }));
        show("Targets saved only on this browser. No workout sets were logged.");
      } else {
        window.localStorage.removeItem(key);
        show("No targets saved. No workout sets were logged.");
      }
    } catch (_) {
      show("Browser storage is unavailable; targets remain editable but will not persist.");
    }
  }
  for (const row of rows) {
    for (const input of row.querySelectorAll("[data-field665]")) {
      input.addEventListener("change", persist);
    }
  }
  if (clear) {
    clear.addEventListener("click", () => {
      try {
        window.localStorage.removeItem(key);
      } catch (_) {
        show("Browser storage is unavailable. Clear visible inputs manually.");
        return;
      }
      for (const row of rows) {
        for (const input of row.querySelectorAll("[data-field665]")) {
          input.value = "";
        }
      }
      show("All saved targets for this routine cleared on this browser.");
    });
  }
})();
