/* Release 667: explicit opt-in copy from frozen goals into editable set fields.
   Does not submit, mark complete, or create sets. */
(() => {
  "use strict";
  const panel = document.getElementById("workout667-active-goal");
  const button = document.getElementById("workout667-use-goal");
  const form = document.getElementById("workout659-log-form");
  if (!panel || !button || !form) return;
  const weight = form.querySelector('input[name="weight_lb"]');
  const reps = form.querySelector('input[name="reps"]');
  if (!weight || !reps) return;

  button.addEventListener("click", () => {
    const load = Number(panel.dataset.plannedLb);
    const count = Number(panel.dataset.plannedReps);
    if (!Number.isFinite(load) || load < 0 || load > 2000 ||
        !Number.isInteger(count) || count < 1 || count > 200) return;
    weight.value = String(load);
    reps.value = String(count);
    weight.dispatchEvent(new Event("input", {bubbles: true}));
    reps.dispatchEvent(new Event("input", {bubbles: true}));
    button.textContent = "Planned values copied — review and Save Set";
    weight.focus();
  });
})();
