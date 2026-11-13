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
    // Keep the dock hidden until a pointer interaction finishes. Otherwise
    // focusing a button blurs the search input, reveals the fixed dock on the
    // next animation frame, and covers the button between pointerdown and
    // click. This can silently swallow the intended button action.
    let pointerInFlight = false;
    document.addEventListener("pointerdown", () => {
      pointerInFlight = true;
    }, true);
    const finishPointer = () => {
      requestAnimationFrame(() => {
        pointerInFlight = false;
        refreshKeyboardState();
      });
    };
    document.addEventListener("pointerup", finishPointer, true);
    document.addEventListener("pointercancel", finishPointer, true);

    // Keyboard-driven focus changes still update immediately. During a
    // pointer transition, defer revealing the dock until the click finishes;
    // moving focus INTO an editable field can hide it right away.
    document.addEventListener("focusin", () => {
      if (pointerInFlight && !isEditingField(document.activeElement)) return;
      refreshKeyboardState();
    });
    document.addEventListener("focusout", () => {
      requestAnimationFrame(() => {
        if (!pointerInFlight) refreshKeyboardState();
      });
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
