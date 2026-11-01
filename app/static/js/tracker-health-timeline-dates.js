/* Keep preset selection and custom date fields in sync without network calls. */
(() => {
  "use strict";
  const form = document.getElementById("health-timeline-filters");
  if (!form) return;
  const period = form.elements.namedItem("days");
  const from = form.elements.namedItem("start_date");
  const through = form.elements.namedItem("end_date");
  if (!period || !from || !through) return;
  for (const input of [from, through]) {
    input.addEventListener("change", () => {
      if (from.value || through.value) period.value = "0";
    });
  }
  period.addEventListener("change", () => {
    if (period.value !== "0") {
      from.value = "";
      through.value = "";
    }
  });
})();
