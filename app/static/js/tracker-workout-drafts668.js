/* Release 668: local, manual-only offline set draft.
   Never uses fetch, service workers, or automatic POST. A draft is not a logged set.
   Drafts are keyed to an exact active session and equipment. */
(() => {
  "use strict";
  const root = document.getElementById("workout659-root");
  const form = document.getElementById("workout659-log-form");
  const keep = document.getElementById("workout668-draft-save");
  const restore = document.getElementById("workout668-draft-restore");
  const erase = document.getElementById("workout668-draft-clear");
  const status = document.getElementById("workout668-draft-status");
  if (!root || !form || !keep || !restore || !erase || !status) return;
  const session = root.dataset.sessionId || "";
  const machine = form.querySelector('input[name="equipment_id"]')?.value || "";
  if (!/^\d+$/.test(session) || !/^\d+$/.test(machine)) return;
  const key = "tracker-workout668-draft:" + session + ":" + machine;
  const fields = ["weight_lb", "reps", "effort", "set_type"];
  const node = (name) => form.querySelector('[name="' + name + '"]');
  const read = () => {
    try {
      const value = window.localStorage.getItem(key);
      if (!value) return null;
      const draft = JSON.parse(value);
      if (draft.version !== 1 || draft.session !== session ||
          draft.machine !== machine || !draft.values ||
          typeof draft.values !== "object") return null;
      if (fields.some((field) => typeof draft.values[field] !== "string" ||
            draft.values[field].length > 32)) return null;
      return draft;
    } catch (_) { return null; }
  };
  const refresh = () => {
    const draft = read();
    restore.disabled = !draft;
    erase.disabled = !draft;
    status.textContent = draft ?
      "Unsynced local draft. Restore and save online to create a recorded set." :
      "No local draft. Saving a draft never logs a set.";
  };
  keep.addEventListener("click", () => {
    const values = {};
    for (const name of fields) {
      const field = node(name);
      values[name] = field ? String(field.value).slice(0, 32) : "";
    }
    const pounds = Number(values.weight_lb);
    const reps = Number(values.reps);
    if (!values.weight_lb || !values.reps ||
        !Number.isFinite(pounds) || pounds < 0 || pounds > 2000 ||
        !Number.isInteger(reps) || reps < 1 || reps > 200) {
      status.textContent = "Enter a valid load and repetition count before saving a draft.";
      return;
    }
    try {
      window.localStorage.setItem(key, JSON.stringify({
        version: 1, session, machine, values, savedAt: new Date().toISOString()
      }));
      refresh();
    } catch (_) {
      status.textContent = "Local draft storage is unavailable in this browser.";
    }
  });
  restore.addEventListener("click", () => {
    const draft = read();
    if (!draft) return refresh();
    for (const name of fields) {
      const field = node(name);
      if (field && draft.values[name]) field.value = draft.values[name];
    }
    status.textContent = "Draft restored to editable fields. Review and tap Save Set online.";
  });
  erase.addEventListener("click", () => {
    try { window.localStorage.removeItem(key); } catch (_) { /* optional */ }
    refresh();
  });
  refresh();
})();
