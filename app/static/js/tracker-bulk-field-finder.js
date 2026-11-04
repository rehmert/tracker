/*
 * Find bulk-edit fields without hiding requested changes.
 * This module never submits a form or modifies inventory.
 */
(() => {
  "use strict";

  function init() {
    const form = document.getElementById("bulk-vials");
    const input = document.getElementById("bulk-field-search");
    const clear = document.getElementById("bulk-field-search-clear");
    const status = document.getElementById("bulk-field-search-status");

    if (!form || !input || !clear || !status) return;

    const groups = [
      ...form.querySelectorAll(".bulk-edit-group")
    ];
    const fields = [
      ...form.querySelectorAll(".bulk-edit-field")
    ];

    if (!groups.length || !fields.length) return;

    let searching = false;
    let originalOpen = new Map();

    function fieldMode(field) {
      return field.querySelector('select[name^="mode_"]')?.value
        || "keep";
    }

    function fieldText(field) {
      const label = field.querySelector("span")?.textContent || "";
      const key = field.dataset.bulkField || "";
      return (label + " " + key.replaceAll("_", " "))
        .toLocaleLowerCase();
    }

    function refresh() {
      const query = input.value.trim().toLocaleLowerCase();
      const activeSearch = query.length > 0;

      if (activeSearch && !searching) {
        originalOpen = new Map(
          groups.map(group => [group, group.open])
        );
      }

      let matched = 0;
      let retained = 0;

      for (const field of fields) {
        const matches = !activeSearch ||
          fieldText(field).includes(query);
        const changed = fieldMode(field) !== "keep";

        // Never hide a requested edit just because it
        // does not match the current search query.
        const visible = matches || changed;

        field.hidden = !visible;

        if (activeSearch && matches) matched++;
        if (activeSearch && changed && !matches) retained++;
      }

      for (const group of groups) {
        const visibleFields = [
          ...group.querySelectorAll(".bulk-edit-field")
        ].filter(field => !field.hidden);

        group.hidden = visibleFields.length === 0;

        if (activeSearch && !group.hidden) {
          group.open = true;
        } else if (!activeSearch) {
          group.hidden = false;
          if (searching && originalOpen.has(group)) {
            group.open = originalOpen.get(group);
          }
        }
      }

      searching = activeSearch;
      clear.disabled = !activeSearch;

      if (!activeSearch) {
        status.textContent =
          "Search field names; requested changes remain visible.";
      } else {
        status.textContent =
          matched + " matching field" +
          (matched === 1 ? "" : "s") +
          (retained
            ? " · " + retained +
              " additional requested change" +
              (retained === 1 ? "" : "s") +
              " kept visible"
            : "");
      }
    }

    input.addEventListener("input", refresh);

    input.addEventListener("keydown", event => {
      if (event.key === "Escape" && input.value) {
        event.preventDefault();
        input.value = "";
        refresh();
      }
    });

    clear.addEventListener("click", () => {
      input.value = "";
      refresh();
      input.focus();
    });

    form.addEventListener("change", event => {
      if (event.target.closest(".bulk-edit-field")) {
        refresh();
      }
    });

    // Existing reset and review undo handlers can change
    // fields programmatically; their change events refresh us.
    const reset = document.getElementById("bulk-edits-reset");
    reset?.addEventListener("click", () => queueMicrotask(refresh));

    refresh();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init, {once:true});
  } else {
    init();
  }
})();
