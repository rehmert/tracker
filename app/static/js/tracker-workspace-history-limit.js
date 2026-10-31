/*
 * Tracker Stage 34.14
 * Administration History Display Limit
 *
 * Frontend-only.
 * No changes to administration records.
 */

(() => {
  'use strict';

  const STORAGE_KEY =
    'tracker.doseWorkspace.historyDisplayLimit.v1';

  const VALID_LIMITS = ['10', '25', '50', '100', 'all'];

  function initialize() {
    const table = document.getElementById(
      'tracker-history-table'
    );

    const controls = document.getElementById(
      'tracker-history-controls'
    );

    const search = document.getElementById(
      'tracker-history-search'
    );

    if (!table || !controls || !search) return;

    if (document.getElementById(
      'tracker-history-limit'
    )) return;

    const tbody = table.tBodies[0];

    if (!tbody) return;

    const rows = Array.from(tbody.rows);

    if (!rows.length) return;

    const style = document.createElement('style');

    style.textContent = `
      #tracker-history-limit-control {
        display:inline-flex;
        align-items:center;
        gap:.45rem;
        flex-wrap:wrap;
      }

      #tracker-history-limit {
        min-width:5rem;
        padding:.35rem .5rem;
        border:1px solid var(--border,#ccc);
        border-radius:.4rem;
        background:var(--surface,#fff);
        color:inherit;
        font:inherit;
      }

      #tracker-history-limit-summary {
        font-size:.85rem;
        opacity:.8;
      }
    `;

    document.head.appendChild(style);

    const wrapper = document.createElement('label');
    wrapper.id = 'tracker-history-limit-control';

    const label = document.createElement('span');
    label.textContent = 'Show entries';

    const select = document.createElement('select');
    select.id = 'tracker-history-limit';

    for (const value of VALID_LIMITS) {
      const option = document.createElement('option');

      option.value = value;
      option.textContent =
        value === 'all' ? 'All' : value;

      select.appendChild(option);
    }

    wrapper.append(label, select);

    const summary = document.createElement('span');
    summary.id = 'tracker-history-limit-summary';
    summary.setAttribute('role', 'status');
    summary.setAttribute('aria-live', 'polite');

    controls.append(wrapper, summary);

    function loadLimit() {
      try {
        const saved = localStorage.getItem(STORAGE_KEY);

        return VALID_LIMITS.includes(saved)
          ? saved
          : 'all';
      } catch (_) {
        return 'all';
      }
    }

    function saveLimit(value) {
      try {
        localStorage.setItem(STORAGE_KEY, value);
      } catch (_) {}
    }

    select.value = loadLimit();

    /*
     * Keep track of which rows match the existing
     * history search before applying our own limit.
     */
    const searchMatches = new WeakMap();

    function captureSearchMatches() {
      rows.forEach(row => {
        searchMatches.set(
          row,
          !row.hidden &&
          getComputedStyle(row).display !== 'none'
        );
      });
    }

    function applyLimit() {
      const limit = select.value === 'all'
        ? Infinity
        : Number(select.value);

      const orderedRows = Array.from(tbody.rows);

      let matched = 0;
      let displayed = 0;

      orderedRows.forEach(row => {
        if (!searchMatches.get(row)) {
          row.hidden = true;
          return;
        }

        matched++;

        const show = displayed < limit;

        row.hidden = !show;

        if (show) displayed++;
      });

      summary.textContent =
        `${displayed} displayed of ${matched} matching ` +
        `administrations (${rows.length} loaded).`;

      /*
       * Notify dependent UI without re-triggering
       * the history search event.
       */
      table.dispatchEvent(
        new CustomEvent('tracker:history-limit-changed', {
          bubbles:true,
          detail:{
            displayed,
            matched,
            loaded:rows.length
          }
        })
      );
    }

    /*
     * Search and sorting scripts update visibility
     * synchronously when the search event fires.
     *
     * Capture their result before applying our
     * display limit.
     */
    function refresh() {
      queueMicrotask(() => {
        captureSearchMatches();
        applyLimit();
      });
    }

    search.addEventListener('input', refresh);

    const clear = document.getElementById(
      'tracker-history-clear'
    );

    if (clear) {
      clear.addEventListener('click', refresh);
    }

    select.addEventListener('change', () => {
      saveLimit(select.value);
      applyLimit();
    });

    /*
     * Sorting refreshes the history search, so
     * it automatically refreshes the limit.
     */
    captureSearchMatches();
    applyLimit();
  }

  if (document.readyState === 'loading') {
    document.addEventListener(
      'DOMContentLoaded',
      initialize,
      { once:true }
    );
  } else {
    initialize();
  }
})();
