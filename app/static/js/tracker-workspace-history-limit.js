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
    let refreshGeneration = 0;
    let renderGeneration = 0;

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

    style.textContent += `
      #tracker-history-page-jump {
        display:inline-flex;
        align-items:center;
        gap:.45rem;
        flex-wrap:wrap;
        margin-left:.5rem;
      }

      #tracker-history-page-number {
        width:4.5rem;
        padding:.35rem .5rem;
        border:1px solid var(--border,#ccc);
        border-radius:.4rem;
        background:var(--surface,#fff);
        color:inherit;
        font:inherit;
      }

      #tracker-history-page-number:disabled {
        opacity:.5;
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

    const jump = document.createElement('form');
    jump.id = 'tracker-history-page-jump';

    const jumpLabel = document.createElement('label');
    jumpLabel.htmlFor = 'tracker-history-page-number';
    jumpLabel.textContent = 'Page';

    const pageNumber = document.createElement('input');
    pageNumber.id = 'tracker-history-page-number';
    pageNumber.type = 'number';
    pageNumber.min = '1';
    pageNumber.step = '1';
    pageNumber.value = '1';
    pageNumber.setAttribute(
      'aria-label',
      'Administration history page number'
    );

    const pageGo = document.createElement('button');
    pageGo.type = 'submit';
    pageGo.id = 'tracker-history-page-go';
    pageGo.textContent = 'Go';

    jump.append(jumpLabel, pageNumber, pageGo);
    pagination.append(previous, status, next, jump);

    const firstPage = document.createElement('button');
    firstPage.type = 'button';
    firstPage.id = 'tracker-history-page-first';
    firstPage.textContent = '⇤ First';
    firstPage.setAttribute('aria-label', 'First history page');

    const lastPage = document.createElement('button');
    lastPage.type = 'button';
    lastPage.id = 'tracker-history-page-last';
    lastPage.textContent = 'Last ⇥';
    lastPage.setAttribute('aria-label', 'Last history page');

    pagination.insertBefore(firstPage, previous);
    pagination.insertBefore(lastPage, next.nextSibling);

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
      const query = search.value.trim().toLocaleLowerCase();

      matchingRows = Array.from(tbody.rows).filter(row => {
        return !query ||
          row.textContent.toLocaleLowerCase().includes(query);
      });
    }

    function pageSize() {
      return select.value === 'all'
        ? Infinity
        : Number(select.value);
    }

    function render() {
      renderGeneration += 1;
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

      firstPage.disabled =
        currentPage === 0 || size === Infinity || total === 0;

      lastPage.disabled =
        currentPage >= pages - 1 ||
        size === Infinity ||
        total === 0;

      previous.disabled =
        currentPage === 0 || size === Infinity;

      next.disabled =
        currentPage >= pages - 1 ||
        size === Infinity;

      pageNumber.max = String(pages);
      pageNumber.value = String(currentPage + 1);

      const canJump =
        total > 0 &&
        pages > 1 &&
        size !== Infinity;

      pageNumber.disabled = !canJump;
      pageGo.disabled = !canJump;

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
      const generation = ++refreshGeneration;

      queueMicrotask(() => {
        if (generation !== refreshGeneration) return;

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

    jump.addEventListener('submit', event => {
      event.preventDefault();

      const size = pageSize();
      if (size === Infinity) return;

      const pages = Math.max(
        1,
        Math.ceil(matchingRows.length / size)
      );

      const requested = Number(pageNumber.value);

      if (
        !Number.isFinite(requested) ||
        !Number.isInteger(requested)
      ) {
        pageNumber.value = String(currentPage + 1);
        return;
      }

      currentPage = Math.max(
        0,
        Math.min(pages - 1, requested - 1)
      );

      render();
    });

    firstPage.addEventListener('click', () => {
      if (currentPage === 0) return;

      currentPage = 0;
      render();
    });

    lastPage.addEventListener('click', () => {
      const size = pageSize();

      if (size === Infinity) return;

      const pages = Math.max(
        1,
        Math.ceil(matchingRows.length / size)
      );

      if (currentPage >= pages - 1) return;

      currentPage = pages - 1;
      render();
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
    window.trackerHistoryDiagnostics = () => {
      const size = pageSize();
      const total = matchingRows.length;

      const pages = size === Infinity
        ? 1
        : Math.max(1, Math.ceil(total / size));

      const displayed = Array.from(tbody.rows).filter(
        row =>
          !row.hidden &&
          getComputedStyle(row).display !== 'none'
      ).length;

      return {
        loaded: rows.length,
        matching: total,
        displayed,
        page: currentPage + 1,
        pages,
        pageSize: size === Infinity ? 'all' : size,
        search: search.value,
        refreshGeneration,
        renderGeneration,
        selected: Boolean(
          table.querySelector(
            'tbody tr.tracker-history-selected'
          )
        )
      };
    };

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
