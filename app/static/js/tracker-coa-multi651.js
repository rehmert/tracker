/* Release 651: mobile-friendly multiple test types per COA document. */
(() => {
  "use strict";

  const entries = [...document.querySelectorAll("[data-coa-multi651]")];
  const upload = document.querySelector("[data-coa-multi-upload651]");
  const form = document.querySelector("[data-coa-bulk-form]");
  const save = document.querySelector("[data-coa-bulk-save]");
  const status = document.querySelector("[data-coa-bulk-status]");

  function labels(entry) {
    const selected = [...entry.querySelectorAll("[data-coa-multi-choice]:checked")]
      .map(input => input.value);
    const custom = entry.querySelector("[data-coa-multi-custom]")?.value.trim();
    if (custom) selected.push(custom);
    return selected;
  }

  function summary(entry) {
    const list = labels(entry);
    const title = entry.querySelector("[data-coa-multi-summary]");
    if (title) title.textContent = list.length ? list.join(" · ") : "Select test types";
  }

  function bind(entry, onChange) {
    entry.querySelectorAll("[data-coa-multi-choice]").forEach(checkbox => {
      checkbox.addEventListener("change", () => {
        summary(entry);
        onChange?.();
      });
    });
    entry.querySelector("[data-coa-multi-custom]")?.addEventListener("input", () => {
      summary(entry);
      onChange?.();
    });
    summary(entry);
  }

  // Upload selection is a native form with no JavaScript-only dependency.
  if (upload) bind(upload);

  if (!form || !save || !status || !entries.length) return;
  for (const entry of entries) {
    entry.dataset.savedSelection = JSON.stringify(labels(entry));
  }

  let saving = false;
  const dirty = entry => JSON.stringify(labels(entry)) !== entry.dataset.savedSelection;
  const dirtyCount = () => entries.filter(dirty).length;

  function refresh() {
    if (saving) return;
    const count = dirtyCount();
    save.disabled = count === 0;
    status.textContent = count
      ? `${count} unsaved document test selection${count === 1 ? "" : "s"}`
      : "All test types saved.";
  }

  entries.forEach(entry => bind(entry, refresh));
  refresh();

  form.addEventListener("submit", async event => {
    event.preventDefault();
    if (saving || dirtyCount() === 0) return;
    if (!form.reportValidity()) return;
    saving = true;
    save.disabled = true;
    status.textContent = "Saving all document test types…";
    try {
      const response = await fetch(form.action, {
        method: "POST",
        body: new FormData(form),
        headers: {Accept: "application/json"},
        credentials: "same-origin",
      });
      const result = await response.json();
      if (!response.ok || !result.ok) {
        throw new Error(result.error || "Unable to save document test types.");
      }
      // Complete response is mandatory before baselines are changed.
      for (const entry of entries) {
        if (typeof result.types?.[entry.dataset.attachmentId] !== "string") {
          throw new Error("Incomplete save response; reload to verify.");
        }
      }
      for (const entry of entries) {
        entry.querySelector("[data-coa-original-type]").value =
          result.types[entry.dataset.attachmentId];
        entry.dataset.savedSelection = JSON.stringify(labels(entry));
      }
      saving = false;
      refresh();
      status.textContent = result.updated
        ? `Saved ${result.updated} document test selection${result.updated === 1 ? "" : "s"}.`
        : "No changes to save.";
    } catch (error) {
      saving = false;
      refresh();
      status.textContent = error.message || "Save failed; selections are unchanged.";
      save.disabled = false;
    }
  });
})();
