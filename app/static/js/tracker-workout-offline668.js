/* Release 668: offline queue is explicit and never misrepresents pending
   entries as saved. Each queued UUID is idempotent on the server; session
   mismatch or authentication failure preserves the queue for review. */
(() => {
  "use strict";
  const root = document.getElementById("workout659-root");
  const form = document.getElementById("workout659-log-form");
  const queueButton = document.getElementById("workout668-queue-set");
  const syncButton = document.getElementById("workout668-sync-set");
  const status = document.getElementById("workout668-offline-status");
  if (!root || !form || !queueButton || !syncButton || !status) return;
  const session = root.dataset.sessionId;
  if (!/^[1-9]\d*$/.test(session)) return;
  const key = "tracker.workout668.offline." + session;
  const endpoint = "/workouts/offline/sync";
  let syncing = false;

  function read() {
    try {
      const value = JSON.parse(localStorage.getItem(key) || "[]");
      if (!Array.isArray(value) || value.length > 100) return null;
      if (value.some(row => !row || row.session_id !== session ||
          typeof row.token !== "string" || typeof row.equipment_id !== "string")) return null;
      return value;
    } catch (_) { return null; }
  }
  function write(rows) {
    try {
      localStorage.setItem(key, JSON.stringify(rows));
      return true;
    } catch (_) { return false; }
  }
  function show(message) {
    const rows = read();
    if (rows === null) {
      status.textContent = "Offline queue unavailable. Do not leave the page until entries are recorded.";
      return;
    }
    status.textContent = message + " " + rows.length +
      " set(s) pending locally — NOT yet saved in Tracker.";
  }
  function capture() {
    if (!form.reportValidity()) return false;
    const data = new FormData(form);
    const weight = Number(data.get("weight_lb"));
    const repetitions = Number(data.get("reps"));
    const effort = String(data.get("effort") || "").trim();
    const equipment = String(data.get("equipment_id") || "");
    const kind = String(data.get("set_type") || "working");
    if (!/^[1-9]\d*$/.test(equipment) || !Number.isFinite(weight) ||
        weight < 0 || weight > 2000 || !Number.isInteger(repetitions) ||
        repetitions < 1 || repetitions > 200 || !["warmup","working"].includes(kind) ||
        (effort && (!/^(10|[1-9])$/.test(effort)))) {
      show("Check weight, repetitions, effort, and set type.");
      return false;
    }
    if (!globalThis.crypto?.randomUUID) {
      show("Secure ID generation is unavailable. Cannot safely queue sets.");
      return false;
    }
    const rows = read();
    if (rows === null || rows.length >= 100) {
      show("Offline queue full or unavailable; reconnect before recording more.");
      return false;
    }
    rows.push({
      token: crypto.randomUUID(), session_id: session,
      equipment_id: equipment, weight_lb: String(weight),
      reps: String(repetitions), effort: effort, set_type: kind,
      queued_at: new Date().toISOString()
    });
    if (!write(rows)) {
      show("Could not save local queue; no set has been recorded.");
      return false;
    }
    show("Set queued.");
    return true;
  }
  // Capture phase is ahead of the existing 659 duplicate-submit handler,
  // which honors event.defaultPrevented. The normal online Save Set stays
  // completely unchanged.
  form.addEventListener("submit", event => {
    if (navigator.onLine) return;
    event.preventDefault();
    capture();
  }, true);
  queueButton.addEventListener("click", () => capture());

  async function sync() {
    if (syncing || !navigator.onLine) {
      show("Offline; replay will resume when a connection is available.");
      return;
    }
    const rows = read();
    if (!rows || !rows.length) { show("No queued sets."); return; }
    syncing = true;
    syncButton.disabled = true;
    let success = 0;
    try {
      for (const row of rows) {
        // Keep the queue until this exact receipt is acknowledged by Tracker.
        const body = new FormData();
        for (const field of ["token","session_id","equipment_id","weight_lb","reps","effort","set_type"]) {
          body.set(field, row[field]);
        }
        let response;
        try {
          response = await fetch(endpoint, {
            method: "POST", credentials: "same-origin",
            redirect: "follow", body,
          });
        } catch (_) { show("Connection lost. Pending sets retained."); break; }
        if (!response.ok || !response.headers.get("content-type")?.includes("application/json") ||
            new URL(response.url).pathname !== endpoint) {
          show("Server rejected replay, or login expired. Pending sets retained.");
          break;
        }
        let result;
        try { result = await response.json(); } catch (_) { break; }
        if (!result || result.ok !== true || !Number.isInteger(result.set_id)) break;
        const stored = read();
        if (stored === null || !write(stored.filter(x => x.token !== row.token))) {
          show("Acknowledged but local queue could not update. Replay is idempotent.");
          break;
        }
        success++;
      }
    } finally {
      syncing = false;
      syncButton.disabled = false;
      show(success ? success + " set(s) synced with Tracker." : "No new acknowledgments.");
    }
  }
  syncButton.addEventListener("click", () => { void sync(); });
  window.addEventListener("online", () => { void sync(); });
  show("Ready.");
  if (navigator.onLine && read()?.length) void sync();
})();
