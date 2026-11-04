/*
 * Navigate between calendar days containing visible entries.
 * Read-only: no dose, protocol, or inventory modifications.
 */
(() => {
  "use strict";

  function init() {
    const grid = document.getElementById("calendar-grid");
    const previous = document.getElementById(
      "calendar-previous-matching-day"
    );
    const next = document.getElementById(
      "calendar-next-matching-day"
    );
    const status = document.getElementById(
      "calendar-matching-day-status"
    );
    const search = document.getElementById("calendar-search");
    const filter = document.getElementById(
      "calendar-status-filter"
    );
    const reset = document.getElementById(
      "calendar-reset-filters"
    );

    if (!grid || !previous || !next || !status ||
        !search || !filter || !reset) return;

    const days = [
      ...grid.querySelectorAll(
        ".calendar-day[data-calendar-date]"
      )
    ].filter(day => !day.classList.contains("outside"));

    let matching = [];

    function currentIndex() {
      const id = window.location.hash.slice(1);
      return matching.findIndex(day => day.id === id);
    }

    function update() {
      matching = days.filter(day =>
        [...day.querySelectorAll(".calendar-activity")]
          .some(item => !item.hidden)
      );

      previous.disabled = matching.length === 0;
      next.disabled = matching.length === 0;

      if (!matching.length) {
        status.textContent =
          "No days match the current calendar filters.";
        return;
      }

      const index = currentIndex();
      const count = matching.length;

      if (index >= 0) {
        status.textContent =
          "Day " + (index + 1) + " of " + count +
          " matching dates · " +
          matching[index].dataset.calendarDate;
      } else {
        status.textContent =
          count + " matching date" +
          (count === 1 ? "" : "s") +
          " in this month. Choose Next day to navigate.";
      }
    }

    function navigate(direction) {
      update();

      if (!matching.length) return;

      const index = currentIndex();
      let targetIndex;

      if (index < 0) {
        targetIndex = direction > 0
          ? 0
          : matching.length - 1;
      } else {
        targetIndex = (
          index + direction + matching.length
        ) % matching.length;
      }

      const target = matching[targetIndex];

      // The existing day-context script highlights
      // the selected calendar hash target.
      window.location.hash = target.id;

      if (!target.hasAttribute("tabindex")) {
        target.setAttribute("tabindex", "-1");
      }

      target.scrollIntoView({
        behavior: "auto",
        block: "center"
      });

      target.focus({preventScroll:true});
      update();
    }

    previous.addEventListener(
      "click", () => navigate(-1)
    );
    next.addEventListener(
      "click", () => navigate(1)
    );

    // Loaded after the existing workbench script.
    // Its listeners update item.hidden before ours
    // recalculate the matching dates.
    search.addEventListener("input", update);
    filter.addEventListener("change", update);

    reset.addEventListener(
      "click", () => queueMicrotask(update)
    );

    window.addEventListener("hashchange", update);

    update();
  }

  if (document.readyState === "loading") {
    document.addEventListener(
      "DOMContentLoaded", init, {once:true}
    );
  } else {
    init();
  }
})();
