/*
 * Actionable summary for guided bulk vial edits.
 * Display and navigation only: never submits or writes inventory.
 */
(() => {
  "use strict";

  function init() {
    const form = document.getElementById("bulk-vials");
    const panel = document.getElementById("bulk-editor-panel");
    const list = document.getElementById("bulk-review-shortcut-list");
    const status = document.getElementById("bulk-review-shortcut-status");
    const onlyEdited = document.getElementById("bulk-show-edited-only");

    if (!form || !panel || !list || !status) return;

    function requested() {
      const rows = [];
      for (const field of form.querySelectorAll(".bulk-edit-field")) {
        const mode = field.querySelector('select[name^="mode_"]');
        if (!mode || mode.value === "keep") continue;

        const key = mode.name.slice(5);
        const input = form.elements.namedItem("value_" + key);
        const label = field.querySelector("span")?.textContent.trim() || key;
        const value = String(input?.value ?? "").trim();

        rows.push({
          field, mode, input, label, value,
          clear: mode.value === "clear",
          invalid: mode.value === "set" && !value
        });
      }
      return rows;
    }

    function goTo(item) {
      panel.open = true;
      if (onlyEdited?.checked) {
        onlyEdited.checked = false;
        onlyEdited.dispatchEvent(new Event("change", {bubbles:true}));
      }

      const group = item.field.closest(".bulk-edit-group");
      if (group) group.open = true;

      item.field.scrollIntoView({
        behavior: "auto",
        block: "center"
      });
      (item.input || item.mode).focus({preventScroll:true});
    }

    function button(text, label, action, className) {
      const element = document.createElement("button");
      element.type = "button";
      element.textContent = text;
      element.setAttribute("aria-label", label);
      element.className = className;
      element.addEventListener("click", action);
      return element;
    }

    function render() {
      const changes = requested();
      const selected = Number(
        document.getElementById("bulk-toolbar-count")?.textContent || 0
      );
      const incomplete = changes.filter(row => row.invalid);

      list.replaceChildren();

      if (!changes.length) {
        const empty = document.createElement("p");
        empty.className = "note";
        empty.textContent = "No fields changed. Choose a new value above to begin.";
        list.appendChild(empty);
      }

      for (const item of changes) {
        const row = document.createElement("div");
        row.className = "bulk-review-shortcut";
        if (item.invalid) row.classList.add("bulk-review-incomplete");

        const value = item.clear
          ? "Clear existing value"
          : item.invalid
            ? "Value required"
            : "Set to " + (
                item.value.length > 55
                  ? item.value.slice(0, 55) + "…"
                  : item.value
              );

        const jump = button(
          item.label + " · " + value,
          "Go to bulk edit field " + item.label,
          () => goTo(item),
          "bulk-review-jump"
        );

        const undo = button(
          "Undo",
          "Undo bulk change to " + item.label,
          () => {
            // Reuse the existing guided editor's undo handler.
            // This ensures the editor state stays synchronized.
            const existing = item.field.querySelector(".bulk-edit-undo");
            if (existing && !existing.disabled) {
              existing.click();
            } else {
              item.mode.value = "keep";
              item.mode.dispatchEvent(
                new Event("change", {bubbles:true})
              );
            }
            render();
          },
          "bulk-review-undo"
        );

        row.append(jump, undo);
        list.appendChild(row);
      }

      const amount = changes.length;
      let message =
        selected + " vial" + (selected === 1 ? "" : "s") +
        " selected · " + amount + " field" +
        (amount === 1 ? "" : "s") + " requested";

      if (!selected) message += " · Select at least one vial";
      if (incomplete.length) {
        message += " · " + incomplete.length +
          " field" + (incomplete.length === 1 ? "" : "s") +
          " need a value";
      }

      status.textContent = message;
      status.dataset.ready = String(
        selected > 0 && changes.length > 0 && incomplete.length === 0
      );
    }

    form.addEventListener("input", event => {
      if (event.target.closest(".bulk-edit-field")) render();
    });

    form.addEventListener("change", event => {
      if (event.target.closest(".bulk-edit-field") ||
          event.target === onlyEdited) render();
    });

    document.addEventListener("tracker:bulk-selection-changed", render);

    const reset = document.getElementById("bulk-edits-reset");
    reset?.addEventListener("click", () => queueMicrotask(render));

    render();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init, {once:true});
  } else {
    init();
  }
})();
