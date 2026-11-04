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

    if (!form || !panel || !summary || !details) return;

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
      const site = selectedLabel("site");
      const useRemaining = Boolean(field("use_remaining")?.checked);
      const supplyChecks = [
        ...form.querySelectorAll('input[name="supply_id_used"]:checked')
      ];

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
        ["Disposables", supplyChecks.length
          ? supplyChecks.length + " selected — verify quantities above"
          : "None selected"],
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

      if (!vialId) missing.push("vial");
      if (!when) missing.push("date/time");
      if (!useRemaining &&
          (!Number.isFinite(Number(amount)) || Number(amount) <= 0)) {
        missing.push("positive amount");
      }

      summary.textContent = missing.length
        ? "Review required: " + missing.join(", ")
        : isWaste
          ? "Review waste/discard entry before saving"
          : "Review recorded values before saving";

      panel.dataset.reviewState = missing.length
        ? "incomplete"
        : "ready";
    }

    form.addEventListener("input", render);
    form.addEventListener("change", render);

    // htmx may reset the form after an accepted submission.
    // The panel always reflects the current form, never stale values.
    form.addEventListener("htmx:afterSettle", render);

    render();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init, {once:true});
  } else {
    init();
  }
})();
