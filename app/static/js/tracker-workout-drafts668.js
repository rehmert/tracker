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
      values[name] = name === "set_type" ?
        (form.querySelector('input[name="set_type"]:checked')?.value || "working") :
        (field ? String(field.value).slice(0, 32) : "");
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
      if (name === "set_type") {
        const options = form.querySelectorAll('input[name="set_type"]');
        for (const choice of options) choice.checked = choice.value === draft.values[name];
      } else if (field) field.value = draft.values[name];
    }
    status.textContent = "Draft restored to editable fields. Review and tap Save Set online.";
  });
  erase.addEventListener("click", () => {
    try { window.localStorage.removeItem(key); } catch (_) { /* optional */ }
    refresh();
  });
  // Offline queue is append-only until the server acknowledges each UUID.
  // Never treat network exceptions, authentication redirects, or non-JSON
  // responses as a successful save. Only exact server receipts remove items.
  const queueButton = document.getElementById("workout668-queue-set");
  const syncButton = document.getElementById("workout668-sync-now");
  const syncStatus = document.getElementById("workout668-sync-status");
  const queueKey = "tracker-workout668-queue:" + session;
  let syncing = false;
  const queueRead = () => {
    try {
      const rows = JSON.parse(window.localStorage.getItem(queueKey) || "[]");
      return Array.isArray(rows) && rows.length <= 100 &&
        rows.every(row => row && row.version === 1 &&
          row.session_id === session && /^\d+$/.test(row.equipment_id) &&
          /^[0-9a-f-]{36}$/.test(row.client_key) &&
          row.values && typeof row.values === "object") ? rows : null;
    } catch (_) { return null; }
  };
  const queueStore = rows => window.localStorage.setItem(queueKey, JSON.stringify(rows));
  const displayQueue = extra => {
    if (!syncStatus) return;
    const rows = queueRead();
    syncStatus.textContent = !rows ? "Queue unavailable; nothing synchronized." :
      rows.length + " unconfirmed set(s) on this workout. " + (extra || "");
  };
  const snapshot = () => {
    const values = {};
    for (const name of fields) {
      values[name] = name === "set_type" ?
        (form.querySelector('input[name="set_type"]:checked')?.value || "working") :
        String(node(name)?.value || "");
    }
    const pounds = Number(values.weight_lb);
    const count = Number(values.reps);
    if (!values.weight_lb || !values.reps || !Number.isFinite(pounds) ||
        pounds < 0 || pounds > 2000 || !Number.isInteger(count) ||
        count < 1 || count > 200) return null;
    if (values.effort && (!/^\d+$/.test(values.effort) ||
        Number(values.effort) < 1 || Number(values.effort) > 10)) return null;
    return values;
  };
  async function syncQueue() {
    if (syncing || !window.navigator.onLine) {
      displayQueue(window.navigator.onLine ? "Synchronization already running." :
        "Offline; your queue is retained.");
      return;
    }
    let pending = queueRead();
    if (!pending) return displayQueue("Review local storage before continuing.");
    syncing = true;
    try {
      for (const queued of [...pending]) {
        const body = new URLSearchParams({
          session_id: queued.session_id,
          equipment_id: queued.equipment_id,
          client_key: queued.client_key,
          ...queued.values
        });
        let response;
        try {
          response = await window.fetch("/workouts/quick/offline-sync", {
            method: "POST", body,
            credentials: "same-origin",
            headers: {"X-Tracker-CSRF": window.trackerCsrfToken?.() || ""},
            redirect: "manual"
          });
        } catch (_) {
          displayQueue("Connection unavailable; unconfirmed actions are retained.");
          break;
        }
        // Redirects may indicate expired sessions or authentication failure.
        if (response.status !== 200 ||
            !(response.headers.get("content-type") || "").includes("application/json")) {
          displayQueue("Server rejected or did not acknowledge an action; review active workout.");
          break;
        }
        const answer = await response.json().catch(() => null);
        if (!answer || answer.ok !== true ||
            (!Number.isInteger(answer.set_id) && answer.deleted !== true)) {
          displayQueue("Invalid server acknowledgement; nothing discarded.");
          break;
        }
        const newest = queueRead();
        if (!newest) break;
        pending = newest.filter(row => row.client_key !== queued.client_key);
        queueStore(pending);
        displayQueue(answer.deleted ? "Previously deleted action acknowledged." :
          "Last recorded set #" + answer.set_id + ".");
      }
    } finally {
      syncing = false;
      displayQueue("");
    }
  }
  if (queueButton && syncButton && syncStatus) {
    queueButton.addEventListener("click", () => {
      const values = snapshot();
      const pending = queueRead();
      if (!values || !pending || pending.length >= 100 ||
          typeof window.crypto?.randomUUID !== "function") {
        displayQueue("Cannot queue invalid values or queue at capacity.");
        return;
      }
      pending.push({
        version: 1, session_id: session, equipment_id: machine,
        client_key: window.crypto.randomUUID(), values
      });
      try {
        queueStore(pending);
        displayQueue("Queued, not yet recorded. Sync will retry online.");
        if (window.navigator.onLine) void syncQueue();
      } catch (_) {
        displayQueue("Local storage is unavailable; set was not queued.");
      }
    });
    syncButton.addEventListener("click", () => { void syncQueue(); });
    window.addEventListener("online", () => { void syncQueue(); });
    displayQueue("");
    if (window.navigator.onLine) void syncQueue();
  }
  refresh();
})();
