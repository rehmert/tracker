/* Guided bulk vial editing. Purely client-side; server remains authoritative. */
(() => {
  "use strict";
  function init() {
    const form = document.getElementById("bulk-vials");
    const fields = [...(form?.querySelectorAll(".bulk-edit-field") || [])];
    const count = document.getElementById("bulk-edits-count");
    const detail = document.getElementById("bulk-edits-details");
    const reset = document.getElementById("bulk-edits-reset");
    if (!form || !fields.length || !count || !detail || !reset) return;

    function current() {
      return fields.map(field => {
        const mode = field.querySelector('select[name^="mode_"]');
        const key = mode?.name.slice(5);
        const input = key && form.elements.namedItem("value_" + key);
        const label = field.querySelector("span")?.textContent.trim() || key;
        return {field, mode, input, label};
      });
    }

    function refresh() {
      const active = current().filter(item => item.mode.value !== "keep");
      for (const item of current()) {
        item.field.classList.toggle(
          "bulk-edit-active", item.mode.value !== "keep"
        );
      }
      count.textContent = active.length
        ? active.length + (active.length === 1 ? " field to update" : " fields to update")
        : "No changes requested yet";
      detail.textContent = active.length
        ? active.map(item => item.label + ": " +
            (item.mode.value === "clear" ? "Clear" : "Set")).join(" · ")
        : "Enter a new value or explicitly choose Set or Clear.";
      reset.disabled = active.length === 0;

      for (const group of form.querySelectorAll(".bulk-edit-group")) {
        const n = group.querySelectorAll(".bulk-edit-active").length;
        const existing = group.querySelector(".bulk-edit-group-count");
        if (existing) existing.textContent = n ? n + " edited" : "";
      }
    }

    for (const item of current()) {
      const {mode, input} = item;
      if (!mode || !input) continue;
      // The older V2 handler controls disabled state. Its unchanged fields
      // remain enabled so editing can opt in without selecting Set first.
      input.addEventListener("input", () => {
        if (mode.value === "keep") {
          mode.value = "set";
          mode.dispatchEvent(new Event("change", {bubbles:true}));
        }
        refresh();
      });
      input.addEventListener("change", () => {
        if (mode.value === "keep") {
          mode.value = "set";
          mode.dispatchEvent(new Event("change", {bubbles:true}));
        }
        refresh();
      });
      mode.addEventListener("change", refresh);
    }

    for (const group of form.querySelectorAll(".bulk-edit-group")) {
      const summary = group.querySelector("summary");
      if (!summary || summary.querySelector(".bulk-edit-group-count")) continue;
      const badge = document.createElement("span");
      badge.className = "bulk-edit-group-count";
      summary.appendChild(badge);
    }

    reset.addEventListener("click", () => {
      for (const item of current()) {
        item.mode.value = "keep";
        if (item.input.tagName === "INPUT") item.input.value = "";
        item.mode.dispatchEvent(new Event("change", {bubbles:true}));
      }
      const snapshot = document.getElementById("bulk-preview-snapshot");
      if (snapshot) snapshot.value = "";
      refresh();
    });
    refresh();
  }
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init, {once:true});
  } else {
    init();
  }
})();
