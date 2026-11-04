/* Hypothetical FEFO allocation; never selects actual vials. */
(() => {
  "use strict";

  function init() {
    const root = document.getElementById(
      "pkExpVialEstimates"
    );
    if (!root) return;

    document.addEventListener(
      "tracker:pk-workbench-ready",
      event => {
        const inventory = event.detail.data.inventory;
        root.replaceChildren();

        const title = document.createElement("h3");
        title.textContent =
          "Estimated vial demand and replenishment";
        root.append(title);

        const summary = document.createElement("p");
        summary.textContent =
          "Unfilled projected mass: " +
          inventory.unfilled_replenishment_mg +
          " mg. Indicative cost using historical " +
          "inventory pricing: " +
          (
            inventory.estimated_replenishment_cost == null
              ? "unknown"
              : "$" + inventory.estimated_replenishment_cost
          ) +
          ". Nominal concentration is label-based, " +
          "not a preparation instruction.";
        root.append(summary);

        const table = document.createElement("table");
        const head = document.createElement("tr");

        [
          "Vial",
          "Initial mg",
          "Allocated mg",
          "Remaining mg",
          "Expiry/BUD",
          "Nominal mg/mL"
        ].forEach(label => {
          const th = document.createElement("th");
          th.textContent = label;
          head.append(th);
        });
        table.append(head);

        (inventory.vial_estimates || []).forEach(v => {
          const tr = document.createElement("tr");

          [
            v.label,
            v.initial_mg,
            v.allocated_mg,
            v.remaining_mg,
            v.expiry || "Not recorded",
            v.nominal_mg_per_ml ?? "Unknown"
          ].forEach(value => {
            const td = document.createElement("td");
            td.textContent = String(value);
            tr.append(td);
          });

          table.append(tr);
        });

        const scroller = document.createElement("div");
        scroller.className = "scroll";
        scroller.append(table);
        root.append(scroller);

        const note = document.createElement("p");
        note.className = "note";
        note.textContent =
          "Pooled hypothetical allocation, not sterility, " +
          "compatibility, true remaining volume, purchasing " +
          "advice or selection of an actual vial.";
        root.append(note);
      }
    );
  }

  if (document.readyState === "loading") {
    document.addEventListener(
      "DOMContentLoaded", init, {once: true}
    );
  } else {
    init();
  }
})();
