/* Release 507: accessible mobile dock using the existing navigation.
   No account details, health values, or login tokens are stored on-device. */
(() => {
  "use strict";

  function init() {
    const dock = document.querySelector(".tracker-mobile-dock");
    const more = document.getElementById("tracker-mobile-more");
    const open = document.getElementById("sidebar-open");
    const shell = document.getElementById("app-shell");
    if (!dock || !more || !open || !shell) return;

    const updateMenu = () => {
      const expanded = shell.classList.contains("sidebar-mobile-open");
      more.setAttribute("aria-expanded", String(expanded));
      more.setAttribute("aria-label", expanded ? "Close more pages" : "More pages");
    };

    // Delegate to the proven sidebar behavior; do not create another menu.
    more.addEventListener("click", () => {
      open.click();
      updateMenu();
    });

    const observer = new MutationObserver(updateMenu);
    observer.observe(shell, { attributes: true, attributeFilter: ["class"] });
    updateMenu();

    const isEditingField = element => (
      element && element.matches &&
      element.matches(
        'input:not([type="checkbox"]):not([type="radio"]):not([type="button"]):not([type="submit"]), textarea, select, [contenteditable="true"]'
      )
    );

    function refreshKeyboardState() {
      document.documentElement.classList.toggle(
        "tracker-mobile-editing",
        Boolean(isEditingField(document.activeElement))
      );
    }
    // Focus events allow the action dock to step aside for the on-screen keyboard.
    document.addEventListener("focusin", refreshKeyboardState);
    document.addEventListener("focusout", () => {
      requestAnimationFrame(refreshKeyboardState);
    });
    window.addEventListener("pageshow", () => {
      updateMenu();
      refreshKeyboardState();
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init, { once: true });
  } else {
    init();
  }
})();
