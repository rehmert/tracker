/* Release 674: optional input-fill only; no automatic set creation or writes. */
(() => {
  "use strict";
  function init() {
    const button = document.getElementById("workout674-use-progression");
    const weight = document.getElementById("workout659-weight");
    const reps = document.getElementById("workout659-reps");
    if (!button || !weight || !reps) return;
    button.addEventListener("click", () => {
      const target = Number(button.dataset.weight674);
      const repTarget = Number(button.dataset.reps674);
      if (!Number.isFinite(target) || target < 0 || target > 2000 ||
          !Number.isInteger(repTarget) || repTarget < 1 || repTarget > 200) return;
      weight.value = String(target);
      reps.value = String(repTarget);
      for (const field of [weight, reps]) {
        field.dispatchEvent(new Event("input", { bubbles: true }));
        field.dispatchEvent(new Event("change", { bubbles: true }));
      }
      weight.focus({ preventScroll: true });
    });
  }
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init, { once: true });
  } else init();
})();
