/*
 * Tracker Stage 34.11
 * Sortable Recent Administration History
 *
 * Frontend-only.
 * Preserves existing table rows and action links.
 */

(() => {
  'use strict';

  function initialize() {
    const table = document.getElementById(
      'tracker-history-table'
    );

    if (!table || !table.tBodies.length) return;

    if (table.dataset.trackerHistorySort === '1') {
      return;
    }

    const tbody = table.tBodies[0];

    const headers = Array.from(
      table.querySelectorAll('thead th')
    );

    const columns = [
      { index: 0, type: 'date' },
      { index: 1, type: 'text' },
      { index: 2, type: 'number' },
      { index: 3, type: 'text' }
    ];

    if (headers.length < 4) return;

    table.dataset.trackerHistorySort = '1';

    const style = document.createElement('style');

    style.textContent = `
      #tracker-history-table
      .tracker-history-sort-button {
        display:inline-flex;
        align-items:center;
        gap:.4rem;
        border:0;
        background:transparent;
        color:inherit;
        font:inherit;
        font-weight:inherit;
        cursor:pointer;
        padding:.3rem .15rem;
        text-align:left;
      }

      #tracker-history-table
      .tracker-history-sort-button:hover {
        color:var(--accent,#2563eb);
      }

      #tracker-history-table
      .tracker-history-sort-button:focus-visible {
        outline:2px solid var(--accent,#2563eb);
        outline-offset:2px;
        border-radius:.2rem;
      }

      #tracker-history-table
      .tracker-history-sort-indicator {
        opacity:.6;
        font-size:.8rem;
      }

      #tracker-history-sort-status {
        font-size:.85rem;
        opacity:.8;
        margin:.4rem 0;
      }
    `;

    document.head.appendChild(style);

    const status = document.createElement('div');
    status.id = 'tracker-history-sort-status';
    status.setAttribute('role', 'status');
    status.setAttribute('aria-live', 'polite');

    table.parentElement.insertAdjacentElement(
      'beforebegin',
      status
    );

    const originalRows = Array.from(tbody.rows);

    const originalOrder = new Map();

    originalRows.forEach((row, index) => {
      originalOrder.set(row, index);
    });

    const collator = new Intl.Collator(undefined, {
      numeric: true,
      sensitivity: 'base'
    });

    let activeColumn = null;
    let ascending = true;

    function text(row, index) {
      const cell = row.cells[index];

      return cell
        ? cell.textContent.replace(/\s+/g, ' ').trim()
        : '';
    }

    function numberValue(value) {
      /*
       * Compare the numeric portion of dose amounts.
       * For mixed units, use text as a secondary
       * comparison rather than converting units.
       */
      const match = value.match(
        /[-+]?(?:\d[\d,]*\.?\d*|\.\d+)/
      );

      return match
        ? Number(match[0].replace(/,/g, ''))
        : null;
    }

    function dateValue(value) {
      const trimmed = value.trim();

      /*
       * Support ISO-style dates as well as common
       * localized dates rendered by Tracker.
       */
      const parsed = Date.parse(trimmed);

      return Number.isFinite(parsed)
        ? parsed
        : null;
    }

    function compareRows(a, b, column) {
      const left = text(a, column.index);
      const right = text(b, column.index);

      if (column.type === 'number') {
        const x = numberValue(left);
        const y = numberValue(right);

        if (x !== null && y !== null && x !== y) {
          return x - y;
        }

        if (x !== null && y === null) return -1;
        if (x === null && y !== null) return 1;
      }

      if (column.type === 'date') {
        const x = dateValue(left);
        const y = dateValue(right);

        if (x !== null && y !== null && x !== y) {
          return x - y;
        }

        if (x !== null && y === null) return -1;
        if (x === null && y !== null) return 1;
      }

      return collator.compare(left, right);
    }

    function updateHeaders() {
      columns.forEach(column => {
        const header = headers[column.index];

        const indicator = header.querySelector(
          '.tracker-history-sort-indicator'
        );

        if (activeColumn === column.index) {
          header.setAttribute(
            'aria-sort',
            ascending ? 'ascending' : 'descending'
          );

          if (indicator) {
            indicator.textContent = ascending
              ? '▲'
              : '▼';
          }
        } else {
          header.setAttribute('aria-sort', 'none');

          if (indicator) {
            indicator.textContent = '↕';
          }
        }
      });
    }

    function refreshHistoryNavigation() {
      /*
       * Stage 34.6 keeps its own match list.
       * Trigger its existing search handler after
       * sorting so navigation follows DOM order.
       *
       * This also refreshes the existing counts
       * and Compound Breakdown.
       */
      const search = document.getElementById(
        'tracker-history-search'
      );

      if (search) {
        search.dispatchEvent(
          new Event('input', { bubbles: true })
        );
      }
    }

    function sort(column) {
      const resetRequested =
        table.dataset.trackerHistoryReset === '1';

      if (resetRequested) {
        activeColumn = null;
        table.dataset.trackerHistoryReset = '0';
      }

      if (activeColumn === column.index) {
        ascending = !ascending;
      } else {
        activeColumn = column.index;

        /*
         * Show newest dates first by default.
         * Other columns start ascending.
         */
        ascending = column.type !== 'date';
      }

      const rows = Array.from(tbody.rows);

      rows.sort((a, b) => {
        const result = compareRows(a, b, column);

        if (result !== 0) {
          return ascending ? result : -result;
        }

        return (
          originalOrder.get(a) -
          originalOrder.get(b)
        );
      });

      /*
       * Move existing nodes, preserving their
       * event listeners, selection, and links.
       */
      const fragment = document.createDocumentFragment();

      rows.forEach(row => fragment.appendChild(row));

      tbody.appendChild(fragment);

      updateHeaders();

      const heading = headers[column.index]
        .querySelector('button')
        ?.textContent
        .replace(/[▲▼↕]/g, '')
        .trim() || 'Column';

      status.textContent =
        `Sorted by ${heading}, ` +
        (ascending ? 'ascending' : 'descending') + '.';

      refreshHistoryNavigation();
    }

    columns.forEach(column => {
      const header = headers[column.index];

      const label = header.textContent.trim();

      const button = document.createElement('button');

      button.type = 'button';
      button.className = 'tracker-history-sort-button';

      const title = document.createElement('span');
      title.textContent = label;

      const indicator = document.createElement('span');
      indicator.className =
        'tracker-history-sort-indicator';
      indicator.textContent = '↕';
      indicator.setAttribute('aria-hidden', 'true');

      button.append(title, indicator);

      button.setAttribute(
        'aria-label',
        `Sort by ${label}`
      );

      button.addEventListener('click', () => {
        sort(column);
      });

      header.replaceChildren(button);
      header.setAttribute('aria-sort', 'none');
    });

    /*
     * Preserve the server's original ordering
     * until the user chooses a sort column.
     */
    status.textContent =
      'Select a column heading to sort administrations.';
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
