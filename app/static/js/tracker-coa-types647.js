/* Release 647: edit all COA document test types, save once, never jump/reload. */
(() => {
  "use strict";

  function setupCustom(entry) {
    const select = entry.querySelector("[data-coa-test-type-select]");
    const wrapper = entry.querySelector("[data-coa-custom-container]");
    const field = wrapper?.querySelector('input[name^="custom_test_type"]');
    if (!select || !wrapper || !field) return;
    const isBulk = entry.hasAttribute("data-coa-type-entry");
    const refresh = (focus = false) => {
      const custom = select.value === "__custom__";
      wrapper.hidden = !custom;
      // Batch posts include the empty custom value for every row. The upload
      // form keeps the earlier disabled-when-hidden semantics.
      field.disabled = !isBulk && !custom;
      field.required = custom;
      if (custom && focus) field.focus({preventScroll: true});
    };
    select.addEventListener("change", () => refresh(true));
    refresh();
  }

  document.querySelectorAll("[data-coa-type-entry]").forEach(setupCustom);
  document.querySelectorAll(".coa-attachment-upload[data-coa-test-type-form]").forEach(setupCustom);

  const form = document.querySelector("[data-coa-bulk-form]");
  const save = document.querySelector("[data-coa-bulk-save]");
  const status = document.querySelector("[data-coa-bulk-status]");
  if (!form || !save || !status) return;

  const entries = [...document.querySelectorAll("[data-coa-type-entry]")];
  const value = entry => {
    const select = entry.querySelector("[data-coa-test-type-select]");
    return select.value === "__custom__"
      ? entry.querySelector('input[name^="custom_test_type"]').value.trim()
      : select.value;
  };
  const baseline = entry => entry.querySelector("[data-coa-original-type]").value;
  const dirtyCount = () => entries.filter(entry => value(entry) !== baseline(entry)).length;
  let saving = false;

  function updateStatus() {
    if (saving) return;
    const changed = dirtyCount();
    save.disabled = changed === 0;
    status.textContent = changed
      ? `${changed} unsaved test type change${changed === 1 ? "" : "s"}`
      : "All test types saved.";
  }
  entries.forEach(entry => {
    entry.querySelector("[data-coa-test-type-select]").addEventListener("change", updateStatus);
    entry.querySelector('input[name^="custom_test_type"]').addEventListener("input", updateStatus);
  });
  updateStatus();

  form.addEventListener("submit", async event => {
    event.preventDefault();
    if (saving || dirtyCount() === 0) return;
    // Native HTML form validation for any visible custom inputs.
    if (!form.reportValidity()) return;
    saving = true;
    save.disabled = true;
    status.textContent = "Saving all test types…";
    try {
      const response = await fetch(form.action, {
        method: "POST",
        body: new FormData(form),
        headers: {Accept: "application/json"},
        credentials: "same-origin",
      });
      const result = await response.json();
      if (!response.ok || !result.ok) {
        throw new Error(result.error || "Unable to save test types.");
      }
      for (const entry of entries) {
        const id = entry.dataset.attachmentId;
        const label = result.types[id];
        if (typeof label !== "string") throw new Error("Incomplete save response; reload to verify.");
        entry.querySelector("[data-coa-original-type]").value = label;
      }
      saving = false;
      updateStatus();
      status.textContent = result.updated
        ? `Saved ${result.updated} test type${result.updated === 1 ? "" : "s"}.`
        : "No changes to save.";
    } catch (error) {
      saving = false;
      updateStatus();
      status.textContent = error.message || "Save failed; your selections are still here.";
      save.disabled = false;
    }
  });
})();
