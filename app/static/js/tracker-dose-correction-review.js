/*
 * Read-only review of corrected disposable usage.
 * Never changes form fields, submits forms, or writes inventory.
 * Server-side inventory validation remains authoritative.
 */
(() => {
  "use strict";

  function init() {
    const form = document.getElementById(
      "tracker-dose-correction-form"
    );
    const panel = document.getElementById(
      "tracker-dose-correction-review"
    );

    if (!form || !panel) return;

    function render() {
      const selected = [
        ...form.querySelectorAll(
          'input[name="supply_id_used"]:checked'
        )
      ];

      const issues = [];

      for (const checkbox of selected) {
        const row = checkbox.closest("tr");
        const input = form.elements.namedItem(
          "supply_qty_" + checkbox.value
        );

        const name = row?.querySelectorAll("td")[1]
          ?.textContent?.trim() ||
          "Supply #" + checkbox.value;

        const raw = String(input?.value ?? "").trim();
        const qty = Number(raw);

        if (
          !raw ||
          !Number.isFinite(qty) ||
          qty <= 0
        ) {
          issues.push(
            name + ": enter a positive quantity"
          );
          continue;
        }

        if (
          input?.dataset.counted === "true" &&
          !Number.isInteger(qty)
        ) {
          issues.push(
            name + ": a whole-number quantity is required"
          );
        }

        // Raw total is provided by the server template.
        // It includes original usage credit where applicable.
        const availableRaw = input?.dataset.available;
        const available = Number(availableRaw);

        if (
          availableRaw !== undefined &&
          availableRaw !== "" &&
          Number.isFinite(available) &&
          qty > available + 1e-9
        ) {
          issues.push(
            name + ": " + qty +
            " requested, " + available + " available"
          );
        }
      }

      panel.replaceChildren();

      const summary = document.createElement("p");

      if (!selected.length) {
        summary.textContent =
          "No disposables selected. No disposable usage will " +
          "be recorded for this corrected entry.";
      } else if (!issues.length) {
        summary.textContent =
          selected.length + " selected supply " +
          (selected.length === 1 ? "type" : "types") +
          "; quantities pass this preliminary review.";
      } else {
        summary.textContent =
          issues.length + " quantity " +
          (issues.length === 1 ? "issue" : "issues") +
          " to review before saving.";

        const list = document.createElement("ul");

        for (const issue of issues) {
          const entry = document.createElement("li");
          entry.textContent = issue;
          list.appendChild(entry);
        }

        panel.appendChild(list);
      }

      panel.prepend(summary);

      panel.dataset.reviewState =
        issues.length ? "incomplete" : "ready";
    }

    form.addEventListener("input", render);
    form.addEventListener("change", render);
    render();
  }

  if (document.readyState === "loading") {
    document.addEventListener(
      "DOMContentLoaded", init, { once: true }
    );
  } else {
    init();
  }
})();
