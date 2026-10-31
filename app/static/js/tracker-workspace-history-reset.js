/*
 * Tracker Stage 34.12
 * Restore original administration history order.
 *
 * Read-only frontend enhancement.
 */

(() => {
  'use strict';

  function initialize() {
    const table = document.getElementById(
      'tracker-history-table'
    );

    const search = document.getElementById(
      'tracker-history-search'
    );

    const status = document.getElementById(
      'tracker-history-sort-status'
    );

    if (!table || !table.tBodies.length || !status) {
      return;
    }

    if (document.getElementById(
      'tracker-history-reset-sort'
    )) {
      return;
    }

    const tbody = table.tBodies[0];

    /*
     * Capture the initial server-provided order.
     * The sorting feature does not reorder rows
     * until a column heading is clicked.
     */
    const originalRows = Array.from(tbody.rows);

    const button = document.createElement('button');
    button.type = 'button';
    button.id = 'tracker-history-reset-sort';
    button.textContent = 'Reset Sort';
    button.disabled = true;

    const style = document.createElement('style');

    style.textContent = `
      #tracker-history-reset-sort {
        margin-left:.75rem;
        padding:.3rem .65rem;
        border:1px solid var(--border,#ccc);
        border-radius:.4rem;
        background:transparent;
        color:inherit;
        font:inherit;
        cursor:pointer;
      }

      #tracker-history-reset-sort:disabled {
        opacity:.45;
        cursor:default;
      }

      #tracker-history-reset-sort:focus-visible {
        outline:2px solid var(--accent,#2563eb);
        outline-offset:2px;
      }
    `;

    document.head.appendChild(style);
    status.appendChild(button);

    function refreshNavigation() {
      if (!search) return;

      /*
       * Stage 34.6 rebuilds its match list when
       * the search input event fires.
       */
      search.dispatchEvent(
        new Event('input', { bubbles:true })
      );
    }

    function resetSort() {
      const fragment = document.createDocumentFragment();

      originalRows.forEach(row => {
        if (row.parentElement === tbody) {
          fragment.appendChild(row);
        }
      });

      tbody.appendChild(fragment);

      table.querySelectorAll(
        'thead th[aria-sort]'
      ).forEach(header => {
        header.setAttribute('aria-sort', 'none');

        const indicator = header.querySelector(
          '.tracker-history-sort-indicator'
        );

        if (indicator) {
          indicator.textContent = '↕';
        }
      });

      button.disabled = true;
      table.dataset.trackerHistoryReset = '1';

      status.firstChild
        ? status.firstChild.textContent =
            'Original administration order restored. '
        : null;

      refreshNavigation();
    }

    button.addEventListener('click', resetSort);

    table.querySelectorAll(
      '.tracker-history-sort-button'
    ).forEach(sortButton => {
      sortButton.addEventListener('click', () => {
        button.disabled = false;
      });
    });
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
