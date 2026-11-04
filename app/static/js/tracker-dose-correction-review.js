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
      const issueControls = [];

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
          issueControls.push(input);
          continue;
        }

        if (
          input?.dataset.counted === "true" &&
          !Number.isInteger(qty)
        ) {
          issues.push(
            name + ": a whole-number quantity is required"
          );
          issueControls.push(input);
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
          issueControls.push(input);
        }
      }

      // Estimate post-correction stock for every affected item.
      // Deselecting an originally used item returns its credit.
      // Do not display estimates while any quantity is invalid.
      const projections = [];
      const movementCounts = {
        returned: 0,
        consumed: 0,
        unchanged: 0
      };

      if (!issues.length) {
        const allChecks = form.querySelectorAll(
          'input[name="supply_id_used"]'
        );

        for (const checkbox of allChecks) {
          const input = form.elements.namedItem(
            "supply_qty_" + checkbox.value
          );

          const availableRaw = input?.dataset.available;
          const originalRaw = input?.dataset.original;
          const available = Number(availableRaw);
          const original = Number(originalRaw);
          const corrected = checkbox.checked
            ? Number(input?.value)
            : 0;

          if (
            availableRaw === undefined ||
            availableRaw === "" ||
            originalRaw === undefined ||
            originalRaw === "" ||
            !Number.isFinite(available) ||
            !Number.isFinite(original) ||
            !Number.isFinite(corrected)
          ) continue;

          if (!checkbox.checked && original <= 0) continue;

          const remaining = available - corrected;
          const row = checkbox.closest("tr");
          const name = row?.querySelectorAll("td")[1]
            ?.textContent?.trim() ||
            "Supply #" + checkbox.value;

          // Limit floating-point display artifacts only.
          const display = number =>
            String(Number(number.toFixed(6)));

          // Net change relative to inventory before correction:
          // restore old usage, then deduct corrected usage.
          const delta = original - corrected;
          const current = available - original;
          const movement = delta > 0
            ? "+" + display(delta) + " returned"
            : delta < 0
              ? "-" + display(-delta) + " consumed"
              : "unchanged";

          if (delta > 0) {
            movementCounts.returned += 1;
          } else if (delta < 0) {
            movementCounts.consumed += 1;
          } else {
            movementCounts.unchanged += 1;
          }

          projections.push(
            name + ": " +
            display(remaining) + " remaining " +
            "(" + display(available) +
            " available - " + display(corrected) +
            " corrected usage)" +
            " · " + movement +
            " from " + display(current) + " current stock"
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

        const firstIssueControl = issueControls[0];

        if (firstIssueControl) {
          const jump = document.createElement("button");
          jump.type = "button";
          jump.textContent = "Go to first quantity issue";

          jump.addEventListener("click", () => {
            const section = firstIssueControl.closest("details");
            if (section) section.open = true;
            firstIssueControl.focus();
          });

          panel.appendChild(jump);
        }
      }

      panel.prepend(summary);

      if (!issues.length && projections.length) {
        const heading = document.createElement("p");
        heading.textContent =
          "Estimated stock after correction (before other activity):";

        const list = document.createElement("ul");

        for (const projection of projections) {
          const item = document.createElement("li");
          item.textContent = projection;
          list.appendChild(item);
        }

        const movementSummary = document.createElement("p");

        movementSummary.textContent =
          "Inventory impact: " +
          movementCounts.returned +
          " supply types returning stock · " +
          movementCounts.consumed +
          " consuming stock · " +
          movementCounts.unchanged +
          " unchanged.";

        panel.append(heading, list);
        panel.insertBefore(movementSummary, heading);
      }

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
