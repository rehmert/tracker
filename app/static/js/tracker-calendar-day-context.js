/*
 * Read-only calendar day summaries.
 * Counts reflect visible calendar events and are not
 * clinical verification or dose-record operations.
 */
(() => {
  "use strict";

  function init() {
    const grid = document.getElementById("calendar-grid");
    const search = document.getElementById("calendar-search");
    const filter = document.getElementById("calendar-status-filter");
    const reset = document.getElementById("calendar-reset-filters");

    if (!grid || !search || !filter || !reset) return;

    const days = [
      ...grid.querySelectorAll(
        ".calendar-day[data-calendar-date]"
      )
    ];

    function update() {
      for (const day of days) {
        let summary = day.querySelector(
          ".tracker-day-event-summary"
        );

        if (!summary) {
          summary = document.createElement("div");
          summary.className = "tracker-day-event-summary";
          summary.setAttribute(
            "aria-label",
            "Visible planned and recorded entries"
          );

          const heading = day.querySelector("strong");
          if (heading) {
            heading.insertAdjacentElement("afterend", summary);
          } else {
            day.prepend(summary);
          }
        }

        let planned = 0;
        let recorded = 0;

        for (const item of day.querySelectorAll(
          ".calendar-activity"
        )) {
          if (item.hidden) continue;

          const status = item.dataset.calendarStatus;

          if (["due", "upcoming", "unrecorded"].includes(status)) {
            planned += 1;
          } else if (["recorded", "extra"].includes(status)) {
            recorded += 1;
          }
        }

        summary.replaceChildren();

        if (!planned && !recorded) {
          summary.hidden = true;
          continue;
        }

        summary.hidden = false;

        const plannedLabel = document.createElement("span");
        plannedLabel.className = "tracker-day-planned";
        plannedLabel.textContent =
          planned + " planned";

        const recordedLabel = document.createElement("span");
        recordedLabel.className = "tracker-day-recorded";
        recordedLabel.textContent =
          recorded + " recorded";

        summary.append(plannedLabel, recordedLabel);
      }
    }

    function highlightReturn() {
      for (const day of days) {
        day.classList.remove("tracker-calendar-return-day");
      }

      const match = /^#calendar-day-(\d{4}-\d{2}-\d{2})$/
        .exec(window.location.hash);

      if (!match) return;

      const target = document.getElementById(
        "calendar-day-" + match[1]
      );

      if (target && grid.contains(target)) {
        target.classList.add("tracker-calendar-return-day");
      }
    }

    // The existing workbench handles event filtering.
    // Register after it and read the resulting hidden states.
    search.addEventListener("input", update);
    filter.addEventListener("change", update);
    reset.addEventListener("click", () => queueMicrotask(update));

    window.addEventListener("hashchange", highlightReturn);

    update();
    highlightReturn();
  }

  if (document.readyState === "loading") {
    document.addEventListener(
      "DOMContentLoaded", init, {once:true}
    );
  } else {
    init();
  }
})();
