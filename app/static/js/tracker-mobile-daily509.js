/* Release 509: thumb-friendly vitals capture; no cached record data. */
(() => {
  "use strict";

  function init() {
    const root = document.querySelector("[data-mobile-daily509]");
    const form = root?.querySelector("[data-daily-vitals-form]");
    if (!form) return;

    const buttons = [...root.querySelectorAll("[data-daily-mode]")];
    const status = root.querySelector("[data-daily-status]");
    const fields = {
      weight: ["weight"],
      bp: ["systolic", "diastolic"],
      pulse: ["pulse"],
      all: ["weight", "systolic", "diastolic", "pulse"]
    };
    const measurementNames = fields.all;
    const field = name => form.elements.namedItem(name);

    function chooseMode(requested, focus = false) {
      const allowed = fields[requested] || fields.all;
      const otherEntered = measurementNames.some(name => (
        !allowed.includes(name) && String(field(name)?.value || "").trim() !== ""
      ));
      // Never submit a filled-out measurement that the UI conceals.
      const mode = otherEntered ? "all" : requested;
      form.dataset.mode = mode;
      for (const button of buttons) {
        button.setAttribute("aria-pressed", String(button.dataset.dailyMode === mode));
      }
      if (status) {
        status.textContent = otherEntered
          ? "Other measurements are filled in, so all values remain visible for review."
          : "";
      }
      if (focus && mode !== "all") {
        const selected = (mode === "bp" ? "systolic" : mode);
        field(selected)?.focus({ preventScroll: true });
      }
      return mode;
    }

    for (const button of buttons) {
      button.addEventListener("click", () => {
        chooseMode(button.dataset.dailyMode, true);
      });
    }

    for (const link of root.querySelectorAll("[data-daily-mode-link]")) {
      link.addEventListener("click", () => {
        chooseMode(link.dataset.dailyModeLink, false);
      });
    }

    // Never erase values when switching modes or returning from another page.
    const initialMode = window.matchMedia("(max-width: 760px)").matches ? "weight" : "all";
    chooseMode(initialMode);

    form.addEventListener("submit", event => {
      if (form.dataset.submitting === "yes") {
        event.preventDefault();
        return;
      }
      const entered = measurementNames.filter(name =>
        String(field(name)?.value || "").trim() !== ""
      );
      if (!entered.length) {
        event.preventDefault();
        chooseMode("all");
        if (status) status.textContent = "Enter a weight, a blood pressure, or a pulse before saving.";
        field("weight")?.focus();
        return;
      }
      if (status) status.textContent = "Saving reading…";
      form.dataset.submitting = "yes";
      const button = form.querySelector('button[type="submit"]');
      if (button) button.disabled = true;
    });

    window.addEventListener("pageshow", () => {
      form.dataset.submitting = "";
      const button = form.querySelector('button[type="submit"]');
      if (button) button.disabled = false;
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init, { once: true });
  } else {
    init();
  }
})();
