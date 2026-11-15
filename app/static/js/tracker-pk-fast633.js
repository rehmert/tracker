/* Release 633: navigation only; never sends requests or changes PK models. */
(() => {
  "use strict";
  function init() {
    const nav = document.querySelector(".pk633-fast-path");
    const status = document.getElementById("pk633NavStatus");
    if (!nav || !status) return;
    nav.addEventListener("click", event => {
      const button = event.target.closest("button[data-pk633-jump]");
      if (!button || !nav.contains(button)) return;
      const id = button.dataset.pk633Jump;
      const mode = button.dataset.pk633Mode;
      if (mode) {
        const tab = document.querySelector('.pk-tab[data-pk-mode="' + mode + '"]');
        if (!tab) return;
        tab.click();
      }
      const destination = document.getElementById(id);
      if (!destination) return;
      destination.scrollIntoView({block: "start", behavior: "auto"});
      status.textContent = id === "pkResults"
        ? "Graph area selected. Run a simulation above to update the modeled curve."
        : "Selected " + button.textContent.trim() + ".";
    });
  }
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init, {once: true});
  } else init();
})();
