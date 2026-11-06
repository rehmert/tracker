/* Release 447: use the established cross-filter vial selection for printing. */
(() => {
  "use strict";
  function ready() {
    const button = document.getElementById("bulk-print-labels447");
    const count = document.getElementById("bulk-toolbar-count");
    const form = document.getElementById("bulk-vials");
    const message = document.getElementById("bulk-print-labels-help447");
    if (!button || !form || !count) return;

    function selectedIds() {
      // Existing selection manager persists off-screen IDs as hidden inputs.
      // A checkbox is included only when checked; hidden IDs are selected.
      const inputs = [
        ...document.querySelectorAll("input.bulk-vial-check:checked"),
        ...form.querySelectorAll('input[type="hidden"][name="vial_ids"]'),
      ];
      const ids = new Set();
      for (const input of inputs) {
        const id = String(input.value);
        if (/^[1-9][0-9]*$/.test(id)) ids.add(id);
      }
      return [...ids].sort((a, b) => Number(a) - Number(b));
    }

    function sync() {
      const total = Number(count.textContent) || 0;
      button.disabled = total < 1 || total > 120;
      button.setAttribute(
        "aria-label", "Print labels for " + total + " selected vials"
      );
      if (message) {
        message.textContent = total > 120
          ? "Printing supports up to 120 selected vials at a time."
          : "Select vials across filters, then preview printable strips.";
      }
    }

    document.addEventListener("tracker:bulk-selection-changed", sync);
    new MutationObserver(sync).observe(count, {
      childList: true, characterData: true, subtree: true,
    });

    button.addEventListener("click", () => {
      const ids = selectedIds();
      if (ids.length === 0) return;
      if (ids.length > 120) {
        alert("Select no more than 120 vials for one print job.");
        return;
      }
      const query = new URLSearchParams({
        ids: ids.join(","),
        layout: "10x20x4",
        phase: "auto",
        rotation: "90",
        copies: "1",
      });
      // A user click opens a separate preview tab, leaving selection intact.
      // The backend revalidates every ID in the current scoped database.
      const url = "/vials/labels/sheets?" + query.toString();
      window.open(url, "_blank", "noopener,noreferrer");
    });

    sync();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", ready, {once: true});
  } else {
    ready();
  }
})();
