/*
 * Tracker Stage 34.13
 * Recent Administration History Preferences
 *
 * Browser-local persistence only.
 */

(() => {
  'use strict';

  const STORAGE_KEY =
    'tracker.doseWorkspace.historyPreferences.v1';

  function initialize() {
    const table = document.getElementById(
      'tracker-history-table'
    );

    const search = document.getElementById(
      'tracker-history-search'
    );

    const controls = document.getElementById(
      'tracker-history-controls'
    );

    const reset = document.getElementById(
      'tracker-history-reset-sort'
    );

    if (!table || !search || !controls || !reset) {
      return;
    }

    if (document.getElementById(
      'tracker-history-forget-preferences'
    )) {
      return;
    }

    const sortButtons = Array.from(
      table.querySelectorAll(
        '.tracker-history-sort-button'
      )
    );

    if (sortButtons.length < 4) return;

    const defaults = {
      search: '',
      sortColumn: null,
      sortDirection: null
    };

    let restoring = false;

    function load() {
      try {
        const value = localStorage.getItem(STORAGE_KEY);

        if (!value) return { ...defaults };

        const parsed = JSON.parse(value);

        if (!parsed || typeof parsed !== 'object') {
          return { ...defaults };
        }

        return {
          search:
            typeof parsed.search === 'string'
              ? parsed.search.slice(0, 200)
              : '',

          sortColumn:
            Number.isInteger(parsed.sortColumn) &&
            parsed.sortColumn >= 0 &&
            parsed.sortColumn < 4
              ? parsed.sortColumn
              : null,

          sortDirection:
            ['ascending', 'descending'].includes(
              parsed.sortDirection
            )
              ? parsed.sortDirection
              : null
        };
      } catch (_) {
        return { ...defaults };
      }
    }

    function save() {
      if (restoring) return;

      const sortedHeader = table.querySelector(
        'thead th[aria-sort="ascending"], ' +
        'thead th[aria-sort="descending"]'
      );

      let sortColumn = null;
      let sortDirection = null;

      if (sortedHeader) {
        const headers = Array.from(
          table.querySelectorAll('thead th')
        );

        sortColumn = headers.indexOf(sortedHeader);
        sortDirection = sortedHeader.getAttribute(
          'aria-sort'
        );
      }

      const preferences = {
        search: search.value,
        sortColumn,
        sortDirection
      };

      try {
        localStorage.setItem(
          STORAGE_KEY,
          JSON.stringify(preferences)
        );
      } catch (_) {
        /*
         * Storage may be unavailable in private
         * browsing or restricted environments.
         */
      }
    }

    function dispatchSearch() {
      search.dispatchEvent(
        new Event('input', { bubbles:true })
      );
    }

    function restore() {
      const preferences = load();

      restoring = true;

      try {
        search.value = preferences.search;
        dispatchSearch();

        if (
          preferences.sortColumn !== null &&
          preferences.sortDirection !== null
        ) {
          const index = preferences.sortColumn;
          const button = sortButtons[index];

          if (button) {
            /*
             * First click applies the default sort.
             * A second click reverses it if needed.
             */
            button.click();

            const header = button.closest('th');

            if (
              header &&
              header.getAttribute('aria-sort') !==
                preferences.sortDirection
            ) {
              button.click();
            }
          }
        }
      } finally {
        restoring = false;
      }
    }

    const forget = document.createElement('button');

    forget.type = 'button';
    forget.id = 'tracker-history-forget-preferences';
    forget.textContent = 'Forget Preferences';

    forget.title =
      'Clear saved history search and sorting preferences';

    const status = document.createElement('span');

    status.id = 'tracker-history-preferences-status';
    status.setAttribute('role', 'status');
    status.setAttribute('aria-live', 'polite');

    const style = document.createElement('style');

    style.textContent = `
      #tracker-history-forget-preferences {
        padding:.35rem .65rem;
        border:1px solid var(--border,#ccc);
        border-radius:.4rem;
        background:transparent;
        color:inherit;
        font:inherit;
        cursor:pointer;
      }

      #tracker-history-forget-preferences:hover {
        border-color:var(--accent,#2563eb);
      }

      #tracker-history-forget-preferences:focus-visible {
        outline:2px solid var(--accent,#2563eb);
        outline-offset:2px;
      }

      #tracker-history-preferences-status {
        font-size:.85rem;
        opacity:.8;
      }
    `;

    document.head.appendChild(style);
    controls.append(forget, status);

    forget.addEventListener('click', () => {
      try {
        localStorage.removeItem(STORAGE_KEY);
      } catch (_) {}

      restoring = true;

      try {
        reset.click();

        search.value = '';
        dispatchSearch();
      } finally {
        restoring = false;
      }

      status.textContent =
        'History preferences cleared.';
    });

    search.addEventListener('input', save);

    sortButtons.forEach(button => {
      button.addEventListener('click', save);
    });

    reset.addEventListener('click', save);

    /*
     * The other history scripts use deferred loading.
     * Restore after all controls have initialized.
     */
    restore();
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
