/* Guided bulk vial editing. Purely client-side; server remains authoritative. */
(() => {
  "use strict";
  function init() {
    const form = document.getElementById("bulk-vials");
    const fields = [...(form?.querySelectorAll(".bulk-edit-field") || [])];
    const count = document.getElementById("bulk-edits-count");
    const detail = document.getElementById("bulk-edits-details");
    const reset = document.getElementById("bulk-edits-reset");
    const apply = document.getElementById("bulk-apply");
    const validation = document.getElementById("bulk-edit-validation");
    const impact = document.getElementById("bulk-edit-impact");
    const editsOnly = document.getElementById("bulk-show-edited-only");
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

    function clearField(item) {
      item.mode.value = "keep";
      if (item.input?.tagName === "INPUT") item.input.value = "";
      item.mode.dispatchEvent(new Event("change", {bubbles:true}));
    }

    function refresh() {
      const items = current();
      const active = items.filter(item => item.mode?.value !== "keep");
      for (const item of items) {
        const changed = item.mode?.value !== "keep";
        item.field.classList.toggle("bulk-edit-active", changed);
        const undo = item.field.querySelector(".bulk-edit-undo");
        if (undo) {
          undo.hidden = !changed;
          undo.disabled = !changed;
        }
      }
      count.textContent = active.length
        ? active.length + (active.length === 1 ? " field to update" : " fields to update")
        : "No changes requested yet";
      detail.textContent = active.length
        ? active.map(item => {
            if (item.mode.value === "clear") return item.label + ": Clear";
            const value = String(item.input?.value ?? "").trim();
            const preview = value.length > 48 ? value.slice(0, 48) + "…" : value;
            return item.label + ": Set → " + (preview || "(value required)");
          }).join(" · ")
        : "Enter a new value or explicitly choose Set or Clear.";
      reset.disabled = active.length === 0;
      const invalid = active.filter(item =>
        item.mode.value === "set" && !String(item.input?.value ?? "").trim()
      );
      if (validation) validation.textContent = invalid.length
        ? "Enter a value for " + invalid.map(item=>item.label).join(", ") +
          ", or choose Clear."
        : active.length ? "Ready to preview selected vials." :
          "Choose at least one field to edit.";
      for (const item of items) {
        if (item.input) item.input.setAttribute(
          "aria-invalid", String(invalid.includes(item))
        );
      }
      const selected = Number(document.getElementById("bulk-toolbar-count")?.textContent || "0");
      if (apply) apply.disabled = selected < 1 || !active.length || invalid.length > 0;
      if (impact) {
        const cells = selected * active.length;
        impact.textContent = selected + " selected vial" + (selected === 1 ? "" : "s") +
          " × " + active.length + " requested field" + (active.length === 1 ? "" : "s") +
          " = up to " + cells.toLocaleString() +
          " field values to review. Actual changes are checked in server preview.";
      }
      if (editsOnly) {
        editsOnly.disabled = active.length === 0;
        if (!active.length) editsOnly.checked = false;
        for (const item of items) {
          item.field.hidden = editsOnly.checked && item.mode.value === "keep";
        }
      }

      for (const group of form.querySelectorAll(".bulk-edit-group")) {
        const n = group.querySelectorAll(".bulk-edit-active").length;
        const existing = group.querySelector(".bulk-edit-group-count");
        if (existing) existing.textContent = n ? n + " edited" : "";
      }
    }

    for (const item of current()) {
      const {mode, input, field, label} = item;
      if (!mode || !input) continue;
      const undo = document.createElement("button");
      undo.type = "button";
      undo.className = "bulk-edit-undo";
      undo.textContent = "Undo this field";
      undo.setAttribute("aria-label", "Undo requested change to " + label);
      undo.hidden = true;
      undo.disabled = true;
      undo.addEventListener("click", event => {
        event.preventDefault();
        clearField(item);
        refresh();
        mode.focus({preventScroll:true});
      });
      field.appendChild(undo);
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

    editsOnly?.addEventListener("change", refresh);

    for (const group of form.querySelectorAll(".bulk-edit-group")) {
      const summary = group.querySelector("summary");
      if (!summary || summary.querySelector(".bulk-edit-group-count")) continue;
      const badge = document.createElement("span");
      badge.className = "bulk-edit-group-count";
      summary.appendChild(badge);
    }

    const table = document.getElementById("tracker-vials-sortable");
    const jumpToVials = document.getElementById("bulk-jump-to-vials");
    const backToVials = document.getElementById("bulk-back-to-vials");
    const scrollToTable = () => {
      if (!table) return;
      table.scrollIntoView({behavior:"auto", block:"start"});
      const first = table.querySelector(".bulk-vial-check");
      if (first) first.focus({preventScroll:true});
    };
    jumpToVials?.addEventListener("click", scrollToTable);
    backToVials?.addEventListener("click", scrollToTable);

    for (const button of form.querySelectorAll("[data-bulk-focus-field]")) {
      button.addEventListener("click", () => {
        const key = button.dataset.bulkFocusField;
        if (editsOnly?.checked) {
          editsOnly.checked = false;
          refresh();
        }
        const target = fields.find(field => field.dataset.bulkField === key);
        if (!target) return;
        const group = target.closest(".bulk-edit-group");
        if (group) group.open = true;
        const input = form.elements.namedItem("value_" + key);
        const mode = form.elements.namedItem("mode_" + key);
        // Navigation alone must never opt a field into a mass update.
        // Changing a value or explicitly selecting Set is required.
        (input || mode)?.focus({preventScroll:true});
        target.scrollIntoView({behavior:"auto", block:"nearest"});
        refresh();
      });
    }

    document.addEventListener("tracker:bulk-selection-changed", refresh);

    reset.addEventListener("click", () => {
      for (const item of current()) clearField(item);
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
