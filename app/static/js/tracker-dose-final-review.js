/*
 * Read-only final review of the dose recording form.
 * Does not change input values, submit forms, or write inventory.
 */
(() => {
  "use strict";

  function init() {
    const form = document.querySelector('form[hx-post="/doses"]');
    const panel = document.getElementById("tracker-dose-final-review");
    const summary = document.getElementById("tracker-dose-review-summary");
    const details = document.getElementById("tracker-dose-review-details");
    const firstIssueButton = document.getElementById(
      "tracker-dose-review-first-issue"
    );
    let firstIssue = null;
    let issueIndex = 0;
    let outstandingIssues = [];

    if (!form || !panel || !summary || !details ||
        !firstIssueButton) return;

    const field = name => form.elements.namedItem(name);
    const value = name => String(field(name)?.value ?? "").trim();

    const selectedLabel = name => {
      const control = field(name);
      const option = control?.selectedOptions?.[0];
      return option?.textContent?.trim() || "Not selected";
    };

    function render() {
      const kind = value("kind");
      const vial = selectedLabel("vial_id");
      const vialId = value("vial_id");
      const amount = value("amount");
      const unit = value("unit");
      const when = value("taken_at");
      // Compare only a valid local datetime field value.
      // A future scheduled time is not proof of administration.
      const validLocalTime =
        /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}$/.test(when);
      const parsedTime = validLocalTime ? new Date(when) : null;
      const futureTime = Boolean(
        parsedTime &&
        Number.isFinite(parsedTime.getTime()) &&
        parsedTime.getTime() > Date.now() + 60000
      );

      const site = selectedLabel("site");
      const useRemaining = Boolean(field("use_remaining")?.checked);
      const supplyChecks = [
        ...form.querySelectorAll('input[name="supply_id_used"]:checked')
      ];

      // Read selected supply names and their actual entered
      // quantities. This is informational: the server remains
      // authoritative for supply validation and deductions.
      const supplies = supplyChecks.map(checkbox => {
        const row = checkbox.closest("tr");
        const name = row?.querySelectorAll("td")[1]
          ?.textContent?.trim() || "Supply #" + checkbox.value;
        const input = field("supply_qty_" + checkbox.value);
        const quantity = String(input?.value ?? "").trim();
        const numeric = Number(quantity);
        const invalid = !quantity ||
          !Number.isFinite(numeric) || numeric <= 0;

        // Availability is shown in the table's third cell.
        // Compare only recognizable numeric values.
        const available = row?.querySelectorAll("td")[2]
          ?.textContent?.trim() || "";
        const normalizedAvailable = available.replaceAll(",", "");
        const availableNumber =
          /^(?:\d+)(?:\.\d+)?$/.test(normalizedAvailable)
            ? Number(normalizedAvailable)
            : null;
        const exceeds = !invalid &&
          availableNumber !== null &&
          numeric > availableNumber;

        // The server identifies count-based categories.
        // Do not infer a category's unit from its name.
        const counted = input?.dataset.counted === "true";
        const fractionalCount = !invalid && counted &&
          !Number.isInteger(numeric);

        return {
          name, quantity, invalid, input, exceeds, available,
          fractionalCount
        };
      });

      const invalidSupplies = supplies.filter(item => item.invalid);
      const overdrawnSupplies = supplies.filter(item => item.exceeds);
      const fractionalSupplies = supplies.filter(
        item => item.fractionalCount
      );
      const supplyDescription = supplies.length
        ? supplies.map(item =>
            item.name + " × " +
            (item.invalid
              ? "(quantity required)"
              : item.fractionalCount
                ? item.quantity + " (whole number required)"
                : item.exceeds
                  ? item.quantity + " (only " + item.available + " available)"
                  : item.quantity)
          ).join(" · ")
        : "None selected";

      const isWaste = kind === "waste";
      const type = isWaste
        ? "Wasted or discarded"
        : kind === "dose" ? "Logged dose" : "Unspecified type";

      const amountDescription = useRemaining
        ? "All remaining vial contents (verify amount in preview)"
        : amount && Number(amount) > 0 && Number.isFinite(Number(amount))
          ? `${amount} ${unit}`.trim()
          : "Amount required";

      const rows = [
        ["Entry type", type],
        ["Vial", vialId ? vial : "Select a vial"],
        ["Amount", amountDescription],
        ["Recorded date and time", when ? when.replace("T", " ") : "Enter date and time"],
        ["Injection site", value("site") ? site : "Not recorded"],
        ["Disposables", supplyDescription],
        ["Notes", value("notes") || "No notes entered"],
      ];

      details.replaceChildren();

      for (const [label, content] of rows) {
        const cell = document.createElement("div");
        const term = document.createElement("dt");
        const description = document.createElement("dd");

        term.textContent = label;
        description.textContent = content;

        cell.append(term, description);
        details.appendChild(cell);
      }

      const missing = [];

      if (invalidSupplies.length) {
        missing.push(
          invalidSupplies.length + " supply " +
          (invalidSupplies.length === 1
            ? "quantity"
            : "quantities")
        );
      }

      if (overdrawnSupplies.length) {
        missing.push(
          overdrawnSupplies.length + " supply " +
          (overdrawnSupplies.length === 1
            ? "quantity exceeds available inventory"
            : "quantities exceed available inventory")
        );
      }

      if (fractionalSupplies.length) {
        missing.push(
          fractionalSupplies.length + " counted supply " +
          (fractionalSupplies.length === 1
            ? "quantity must be whole"
            : "quantities must be whole")
        );
      }

      if (!vialId) missing.push("vial");
      if (!when) missing.push("date/time");
      if (futureTime) {
        missing.push("timestamp is in the future — confirm actual time");
      }
      if (!useRemaining &&
          (!Number.isFinite(Number(amount)) || Number(amount) <= 0)) {
        missing.push("positive amount");
      }

      // This navigation does not change the input or
      // submit the form. It only identifies where
      // the first review issue can be addressed.
      const issueTargets = [
        ...invalidSupplies.map(item => item.input),
        ...overdrawnSupplies.map(item => item.input),
        ...fractionalSupplies.map(item => item.input),
        !vialId ? field("vial_id") : null,
        !when ? field("taken_at") : null,
        futureTime ? field("taken_at") : null,
        (!useRemaining &&
          (!Number.isFinite(Number(amount)) || Number(amount) <= 0))
          ? field("amount") : null
      ];

      outstandingIssues = [...new Set(issueTargets.filter(Boolean))];
      issueIndex = 0;
      firstIssue = outstandingIssues[0] || null;
      firstIssueButton.disabled = !firstIssue;
      firstIssueButton.textContent = outstandingIssues.length
        ? "Go to issue 1 of " + outstandingIssues.length
        : "No outstanding review issues";

      summary.textContent = missing.length
        ? "Review required: " + missing.join(", ")
        : isWaste
          ? "Review waste/discard entry before saving"
          : "Review recorded values before saving";

      panel.dataset.reviewState = missing.length
        ? "incomplete"
        : "ready";

      panel.dataset.futureTimestamp = futureTime
        ? "true"
        : "false";
    }

    firstIssueButton.addEventListener("click", () => {
      if (!firstIssue) return;

      // An invalid supply quantity may be inside
      // the collapsed disposables section.
      const disclosure = firstIssue.closest("details");
      if (disclosure) disclosure.open = true;

      firstIssue.scrollIntoView({
        behavior: "auto",
        block: "center"
      });

      firstIssue.focus({preventScroll:true});

      // Move to the next problem on the next click.
      // Focus/navigation alone never changes a form value.
      if (outstandingIssues.length) {
        issueIndex = (issueIndex + 1) % outstandingIssues.length;
        firstIssue = outstandingIssues[issueIndex];
        firstIssueButton.textContent =
          "Go to issue " + (issueIndex + 1) +
          " of " + outstandingIssues.length;
      }
    });

    form.addEventListener("input", render);
    form.addEventListener("change", render);

    // htmx may reset the form after an accepted submission.
    // The panel always reflects the current form, never stale values.
    form.addEventListener("htmx:afterSettle", render);

    // The existing sequential workflow resets the form and
    // issues a new one-use token after a committed recording.
    document.body.addEventListener(
      "tracker:dose-saved",
      () => queueMicrotask(render)
    );

    render();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init, {once:true});
  } else {
    init();
  }
})();
