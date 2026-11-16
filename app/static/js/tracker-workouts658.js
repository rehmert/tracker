/* Release 658: progressive row controls for historical workout entry.
   No API calls: every set is validated and committed atomically by the server. */
(() => {
  "use strict";
  const form = document.getElementById("workout658-form");
  const root = document.getElementById("workout658-rows");
  const template = document.getElementById("workout658-row-template");
  const add = document.getElementById("workout658-add");
  const status = document.getElementById("workout658-row-status");
  const save = document.getElementById("workout658-save");
  if (!form || !root || !template || !add || !status || !save) return;

  const limit = Number(root.dataset.maxRows) || 40;
  function refresh() {
    const rows = Array.from(root.querySelectorAll(".workout658-row"));
    rows.forEach((row, index) => {
      const legend = row.querySelector("legend");
      if (legend) legend.textContent = "Set " + (index + 1);
    });
    add.disabled = rows.length >= limit;
    status.textContent = rows.length + " of " + limit + " possible set rows.";
  }
  add.addEventListener("click", () => {
    if (root.querySelectorAll(".workout658-row").length >= limit) return;
    const row = template.content.firstElementChild.cloneNode(true);
    root.appendChild(row);
    refresh();
    const machine = row.querySelector('select[name="equipment_id"]');
    if (machine) machine.focus();
  });
  root.addEventListener("click", (event) => {
    const target = event.target.closest("[data-remove658]");
    if (!target || !root.contains(target)) return;
    const row = target.closest(".workout658-row");
    if (!row) return;
    if (root.querySelectorAll(".workout658-row").length <= 1) {
      row.querySelectorAll("input").forEach((input) => { input.value = ""; });
      row.querySelectorAll("select").forEach((select) => { select.selectedIndex = 0; });
    } else {
      row.remove();
    }
    refresh();
  });
  form.addEventListener("submit", (event) => {
    if (event.defaultPrevented) return;
    if (form.dataset.submitting658 === "yes") {
      event.preventDefault();
      return;
    }
    form.dataset.submitting658 = "yes";
    save.disabled = true;
    save.textContent = "Saving Workout…";
  });
  refresh();
})();
