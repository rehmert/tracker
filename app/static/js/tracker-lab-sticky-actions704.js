/* Release 704: read-only scroll gate for the original manual Lab actions.
   The separate CSV import form can occupy the first viewport. CSS sticky
   cannot rise above the manual form's top edge, so an action row must not
   become sticky until its own form has entered a safe viewport region.
   No clones, submits, network, storage or changes to Lab validation. */
(() => {
  "use strict";

  function initialize() {
    const form = document.querySelector("form[data-lab-manual-entry]");
    const actions = form?.querySelector(":scope > .tracker-form-actions704--lab");
    const dock = document.querySelector(".tracker-mobile-dock");
    if (!form || !actions || !dock) return;

    let scheduled = false;
    const enabledClass = "tracker-lab-actions704-active";

    function refresh() {
      scheduled = false;
      const narrow = window.matchMedia("(max-width: 760px)").matches;
      const editing = document.documentElement.classList.contains(
        "tracker-mobile-editing"
      );
      // The CSS default is normal flow; do not show a sticky action bar
      // before the manual Lab form has room above the fixed mobile dock.
      if (!narrow || editing || getComputedStyle(dock).display === "none") {
        form.classList.remove(enabledClass);
        return;
      }

      const formTop = form.getBoundingClientRect().top;
      const barHeight = actions.getBoundingClientRect().height;
      const dockTop = dock.getBoundingClientRect().top;

      // Do not activate over the earlier CSV import section even if the
      // form's top is just barely high enough. Require the manual form
      // to reach the upper portion of the viewport first. A 16px margin
      // then maintains safe dock clearance across density changes.
      const manualFormEntered = formTop <= 120;
      const safeToStick = manualFormEntered &&
        formTop + barHeight + 16 <= dockTop;
      form.classList.toggle(enabledClass, safeToStick);
    }

    function schedule() {
      if (scheduled) return;
      scheduled = true;
      window.requestAnimationFrame(refresh);
    }

    window.addEventListener("scroll", schedule, { passive: true });
    window.addEventListener("resize", schedule);
    window.addEventListener("pageshow", schedule);
    document.addEventListener("focusin", schedule);
    document.addEventListener("focusout", schedule);

    // The existing density setting changes geometry without resizing.
    const observer = new MutationObserver(schedule);
    observer.observe(document.documentElement, {
      attributes: true, attributeFilter: ["data-density", "class"]
    });
    schedule();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initialize, { once: true });
  } else {
    initialize();
  }
})();
