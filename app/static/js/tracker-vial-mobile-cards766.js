/* Release 766: cosmetic mobile-only full-table disclosure. No data writes. */
(() => {
  "use strict";
  function init() {
    const button = document.getElementById("vial766-full-toggle");
    const table = document.getElementById("vial766-full-table");
    if (!button || !table) return;
    button.addEventListener("click", () => {
      const expanded = button.getAttribute("aria-expanded") !== "true";
      button.setAttribute("aria-expanded", String(expanded));
      table.classList.toggle("vial766-open", expanded);
      button.textContent = expanded
        ? "Hide Full Table (Compact View)"
        : "Show Full Table and Bulk Selection";
      if (expanded) table.scrollIntoView({block: "nearest"});
    });
    const jump = document.querySelector('a[href="#bulk-selection-toolbar"]');
    if (jump) jump.addEventListener("click", () => {
      table.classList.add("vial766-open");
      button.setAttribute("aria-expanded", "true");
      button.textContent = "Hide Full Table (Compact View)";
    });
  }
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init, {once:true});
  } else init();
})();
