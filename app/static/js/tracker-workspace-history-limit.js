/*
 * Tracker Stage 34.15
 * Administration History Pagination
 *
 * Replaces Stage 34.14 display-limit implementation.
 *
 * No backend or database changes.
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

    const tbody = table.tBodies[0];

    if (!tbody) return;

    const rows = Array.from(tbody.rows);

    if (!rows.length) return;

    if (document.getElementById(
      'tracker-history-limit'
    )) return;

    let currentPage = 0;
    let matchingRows = [];

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

      #tracker-history-pagination {
        display:flex;
        align-items:center;
        flex-wrap:wrap;
        gap:.5rem;
        margin:.75rem 0;
      }

      #tracker-history-pagination button {
        padding:.35rem .7rem;
        border:1px solid var(--border,#ccc);
        border-radius:.4rem;
        background:transparent;
        color:inherit;
        font:inherit;
        cursor:pointer;
      }

      #tracker-history-pagination button:disabled {
        opacity:.4;
        cursor:default;
      }

      #tracker-history-pagination button:focus-visible {
        outline:2px solid var(--accent,#2563eb);
        outline-offset:2px;
      }

      #tracker-history-page-status {
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
    controls.appendChild(wrapper);

    const pagination = document.createElement('div');
    pagination.id = 'tracker-history-pagination';

    const previous = document.createElement('button');
    previous.type = 'button';
    previous.id = 'tracker-history-page-previous';
    previous.textContent = '← Previous Page';

    const next = document.createElement('button');
    next.type = 'button';
    next.id = 'tracker-history-page-next';
    next.textContent = 'Next Page →';

    const status = document.createElement('span');
    status.id = 'tracker-history-page-status';
    status.setAttribute('role', 'status');
    status.setAttribute('aria-live', 'polite');

    pagination.append(previous, status, next);

    const scroll = table.closest('.scroll');

    if (scroll) {
      scroll.insertAdjacentElement(
        'afterend',
        pagination
      );
    } else {
      table.insertAdjacentElement(
        'afterend',
        pagination
      );
    }

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
     * Determine search matches independently of
     * pagination visibility.
     *
     * Stage 34.6 filters administrations using
     * their displayed text. The original search
     * handler runs before this listener.
     */
    function captureMatches() {
      matchingRows = Array.from(tbody.rows).filter(
        row =>
          !row.hidden &&
          getComputedStyle(row).display !== 'none'
      );
    }

    function pageSize() {
      return select.value === 'all'
        ? Infinity
        : Number(select.value);
    }

    function render() {
      const size = pageSize();

      const total = matchingRows.length;

      const pages = size === Infinity
        ? 1
        : Math.max(1, Math.ceil(total / size));

      currentPage = Math.max(
        0,
        Math.min(currentPage, pages - 1)
      );

      const start = size === Infinity
        ? 0
        : currentPage * size;

      const end = size === Infinity
        ? total
        : Math.min(total, start + size);

      const visible = new Set(
        matchingRows.slice(start, end)
      );

      rows.forEach(row => {
        row.hidden = !visible.has(row);
      });

      previous.disabled =
        currentPage === 0 || size === Infinity;

      next.disabled =
        currentPage >= pages - 1 ||
        size === Infinity;

      if (total === 0) {
        status.textContent =
          `No matching administrations (${rows.length} loaded).`;
      } else {
        status.textContent =
          `Showing ${start + 1}–${end} of ${total} ` +
          `matching administrations · Page ` +
          `${currentPage + 1} of ${pages}`;
      }

      /*
       * Notify the individual administration navigator
       * that its visible row set has changed.
       */
      table.dispatchEvent(
        new CustomEvent('tracker:history-navigation-refresh', {
          bubbles: true,
          detail: {
            page: currentPage + 1,
            displayed: visible.size
          }
        })
      );

      table.dispatchEvent(
        new CustomEvent('tracker:history-page-changed', {
          bubbles: true,
          detail: {
            page: currentPage + 1,
            pages,
            matching: total,
            displayed: visible.size,
            loaded: rows.length
          }
        })
      );
    }

    function refresh() {
      /*
       * Let Stage 34.6 complete its search
       * filtering before capturing matches.
       */
      queueMicrotask(() => {
        currentPage = 0;
        captureMatches();
        render();
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
      currentPage = 0;
      saveLimit(select.value);

      /*
       * Restore search-derived visibility before
       * applying the new page size.
       */
      search.dispatchEvent(
        new Event('input', { bubbles: true })
      );
    });

    previous.addEventListener('click', () => {
      if (currentPage <= 0) return;

      currentPage--;
      render();
    });

    next.addEventListener('click', () => {
      const size = pageSize();

      if (size === Infinity) return;

      const pages = Math.ceil(
        matchingRows.length / size
      );

      if (currentPage >= pages - 1) return;

      currentPage++;
      render();
    });

    /*
     * Initial state follows existing search
     * preferences restored by Stage 34.13.
     */
    captureMatches();
    render();
  }

  if (document.readyState === 'loading') {
    document.addEventListener(
      'DOMContentLoaded',
      initialize,
      { once: true }
    );
  } else {
    initialize();
  }
})();
