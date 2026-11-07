/*
 * Release 448: browser-only pagination for the existing filtered vial table.
 *
 * No row removal, network requests, DB writes, or changes to saved selection.
 * All rows remain in the DOM for inventory reports, CSV, sorting and quick-find.
 */
(() => {
  "use strict";

  const STORAGE = "tracker.vials.pageSize448";
  const ALLOWED = new Set([0, 25, 50, 100]);

  function init() {
    const table = document.getElementById("tracker-vials-sortable");
    const controls = document.getElementById("tracker-vial-pager448");
    const select = document.getElementById("tracker-vial-page-size448");
    const info = document.getElementById("tracker-vial-page-info448");
    const first = document.getElementById("tracker-vial-first448");
    const previous = document.getElementById("tracker-vial-prev448");
    const next = document.getElementById("tracker-vial-next448");
    const last = document.getElementById("tracker-vial-last448");

    if (!table || !controls || !select || !info ||
        !first || !previous || !next || !last || !table.tBodies[0]) return;

    let size = 25;
    let page = 0;

    try {
      const stored = Number(sessionStorage.getItem(STORAGE));
      if (ALLOWED.has(stored) && stored !== 0) size = stored;
      else if (sessionStorage.getItem(STORAGE) === "0") size = 0;
    } catch (_) { /* Browser storage may be disabled. */ }

    select.value = String(size);

    function vialRows() {
      // Read fresh DOM order every time: sorting moves rows in the same tbody.
      return Array.from(table.tBodies[0].rows).filter(
        row => row.querySelector("input.bulk-vial-check")
      );
    }

    function render() {
      const rows = vialRows();
      const total = rows.length;
      const per = size === 0 ? Math.max(1, total) : size;
      const pages = Math.max(1, Math.ceil(total / per));
      page = Math.max(0, Math.min(page, pages - 1));
      const start = page * per;
      const end = Math.min(start + per, total);

      rows.forEach((row, index) => {
        row.hidden = index < start || index >= end;
      });

      first.disabled = previous.disabled = page === 0;
      last.disabled = next.disabled = page >= pages - 1;

      info.textContent = total
        ? "Showing " + (start + 1) + "–" + end + " of " + total
            + " vials · page " + (page + 1) + " of " + pages
        : "No vials match the selected filters";

      controls.hidden = false;
      // Update the central cross-view checkbox state, including header select-all.
      document.dispatchEvent(new Event("tracker:vials-page-changed"));
    }

    function goto(newPage) {
      page = newPage;
      render();
    }

    first.addEventListener("click", () => goto(0));
    previous.addEventListener("click", () => goto(page - 1));
    next.addEventListener("click", () => goto(page + 1));
    last.addEventListener("click", () => {
      const count = vialRows().length;
      goto(size === 0 ? 0 : Math.max(0, Math.ceil(count / size) - 1));
    });

    select.addEventListener("change", () => {
      const chosen = Number(select.value);
      if (!ALLOWED.has(chosen)) {
        select.value = String(size);
        return;
      }
      size = chosen;
      page = 0;
      try {sessionStorage.setItem(STORAGE, String(size));}
      catch (_) { /* Pagination must work even without storage. */ }
      render();
    });

    // Column sorting reorders tbody rows. Return to page one of sorted results.
    document.addEventListener("tracker:vials-sorted", () => {
      page = 0;
      render();
    });

    // Both quick-find and attention navigation can jump to any matching row.
    document.addEventListener("tracker:vials-show-row", event => {
      const row = event.detail?.row;
      if (!row) return;
      const rows = vialRows();
      const index = rows.indexOf(row);
      if (index < 0) return;
      page = size === 0 ? 0 : Math.floor(index / size);
      render();
    });

    render();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init, {once: true});
  } else {
    init();
  }
})();
