/*
 * Tracker Batch 51: PK interval selection helpers.
 * Presentation only; the original numeric field remains
 * authoritative for preview, validation, and saved scenarios.
 */
(() => {
  "use strict";

  const presets = Object.freeze([
    ["0.5", "Twice daily (12 hours)"],
    ["1", "Daily"],
    ["2", "Every other day"],
    ["3", "Every 3 days"],
    ["3.5", "Twice weekly (every 3.5 days)"],
    ["4", "Every 4 days"],
    ["5", "Every 5 days"],
    ["7", "Weekly"],
    ["10", "Every 10 days"],
    ["14", "Every 2 weeks"],
    ["21", "Every 3 weeks"],
    ["28", "Every 4 weeks"]
  ]);

  function attach(input, options = {}) {
    if (!input || input.dataset.pkPresetAttached === "1") {
      return null;
    }

    const inherit = options.inherit === true;

    const select = document.createElement("select");
    select.className = "pk-interval-preset";
    select.setAttribute(
      "aria-label",
      inherit
        ? "Stage interval preset"
        : "Dosing interval preset"
    );

    const custom = new Option("Custom interval", "custom");
    select.add(custom);

    if (inherit) {
      select.add(
        new Option("Use schedule default", "inherit")
      );
    }

    presets.forEach(([value, label]) => {
      select.add(new Option(label, value));
    });

    function synchronize() {
      const raw = input.value.trim();

      if (inherit && raw === "") {
        select.value = "inherit";
        return;
      }

      const match = presets.find(
        ([value]) => raw !== "" &&
          Number(value) === Number(raw)
      );

      select.value = match ? match[0] : "custom";
    }

    select.addEventListener("change", () => {
      if (select.value === "custom") {
        input.focus();
        return;
      }

      input.value = select.value === "inherit"
        ? ""
        : select.value;

      // Existing simulation editors invalidate results using
      // these standard events.
      input.dispatchEvent(
        new Event("input", {bubbles:true})
      );
      input.dispatchEvent(
        new Event("change", {bubbles:true})
      );
    });

    input.addEventListener("input", synchronize);
    input.addEventListener("change", synchronize);

    input.dataset.pkPresetAttached = "1";
    input.insertAdjacentElement("afterend", select);

    synchronize();

    return select;
  }

  window.trackerPkIntervalPresets = Object.freeze({
    attach,
    presets
  });
})();
