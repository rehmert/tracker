/* Release 655: avoid accidental repeated form submission on mobile. */
(() => {
  "use strict";
  document.addEventListener("submit", (event) => {
    const form = event.target;
    if (!(form instanceof HTMLFormElement) ||
        !form.classList.contains("workout-repeat655")) return;
    if (form.dataset.submitting655 === "yes") {
      event.preventDefault();
      return;
    }
    form.dataset.submitting655 = "yes";
    const button = form.querySelector("button[type=submit]");
    if (button) {
      button.disabled = true;
      button.textContent = "Recording…";
    }
  });
})();
