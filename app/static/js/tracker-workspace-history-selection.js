/*
 * Tracker Stage 34.17
 * Recent Administration Selection UX
 *
 * Frontend-only.
 * Does not modify administration records.
 */

(() => {
  'use strict';

  function initialize() {
    const table = document.getElementById(
      'tracker-history-table'
    );

    const section = document.getElementById(
      'tracker-history-section'
    );

    if (!table || !section || !table.tBodies.length) {
      return;
    }

    if (document.getElementById(
      'tracker-history-selection'
    )) {
      return;
    }

    const rows = Array.from(
      table.tBodies[0].rows
    ).filter(row => row.cells.length >= 4);

    if (!rows.length) return;

    const style = document.createElement('style');

    style.textContent = `
      #tracker-history-selection {
        display:flex;
        align-items:center;
        justify-content:space-between;
        flex-wrap:wrap;
        gap:.75rem;
        margin:.75rem 0;
        padding:.8rem 1rem;
        border:1px solid var(--border,#ddd);
        border-radius:.65rem;
        background:var(--surface,#fff);
      }

      #tracker-history-selection strong {
        display:block;
        font-size:.85rem;
        margin-bottom:.2rem;
      }

      #tracker-history-selection-details {
        font-size:.9rem;
        overflow-wrap:anywhere;
      }

      #tracker-history-selection-clear {
        padding:.35rem .7rem;
        border:1px solid var(--border,#ccc);
        border-radius:.4rem;
        background:transparent;
        color:inherit;
        font:inherit;
        cursor:pointer;
      }

      #tracker-history-selection-clear:disabled {
        opacity:.45;
        cursor:default;
      }

      #tracker-history-table
      tbody tr.tracker-history-selected {
        outline:2px solid var(--accent,#2563eb);
        outline-offset:-2px;
        background:rgba(59,130,246,.08);
      }

      #tracker-history-table
      tbody tr[data-tracker-history-selectable] {
        cursor:pointer;
      }

      #tracker-history-table
      tbody tr[data-tracker-history-selectable]:focus-visible {
        outline:2px solid var(--accent,#2563eb);
        outline-offset:-2px;
      }
    `;

    document.head.appendChild(style);

    const panel = document.createElement('div');
    panel.id = 'tracker-history-selection';

    const content = document.createElement('div');

    const heading = document.createElement('strong');
    heading.textContent = 'Selected administration';

    const details = document.createElement('div');
    details.id = 'tracker-history-selection-details';
    details.textContent =
      'Select an administration to view its details.';

    content.append(heading, details);

    const clear = document.createElement('button');
    clear.type = 'button';
    clear.id = 'tracker-history-selection-clear';
    clear.textContent = 'Clear Selection';
    clear.disabled = true;

    panel.append(content, clear);

    const scroll = table.closest('.scroll');

    if (scroll) {
      scroll.insertAdjacentElement(
        'beforebegin',
        panel
      );
    } else {
      table.insertAdjacentElement(
        'beforebegin',
        panel
      );
    }

    let selected = null;

    function cellText(row, index) {
      const cell = row.cells[index];

      return cell
        ? cell.textContent.replace(/\s+/g, ' ').trim()
        : '';
    }

    function visibleRows() {
      return Array.from(
        table.tBodies[0].rows
      ).filter(row =>
        !row.hidden &&
        getComputedStyle(row).display !== 'none'
      );
    }

    function selectRow(row, scrollIntoView = false) {
      if (!row || !visibleRows().includes(row)) {
        return;
      }

      rows.forEach(item => {
        item.classList.remove(
          'tracker-history-selected'
        );

        item.removeAttribute('aria-selected');
      });

      selected = row;

      row.classList.add(
        'tracker-history-selected'
      );

      row.setAttribute('aria-selected', 'true');

      const compound = cellText(row, 1);
      const amount = cellText(row, 2);
      const when = cellText(row, 0);
      const site = cellText(row, 3);

      details.textContent =
        `${compound} · ${amount} · ${when} · ${site}`;

      clear.disabled = false;

      if (scrollIntoView) {
        row.scrollIntoView({
          behavior:'smooth',
          block:'nearest'
        });
      }
    }

    function clearSelection() {
      selected = null;

      rows.forEach(row => {
        row.classList.remove(
          'tracker-history-selected'
        );

        row.removeAttribute('aria-selected');
      });

      details.textContent =
        'Select an administration to view its details.';

      clear.disabled = true;
    }

    clear.addEventListener(
      'click',
      clearSelection
    );

    rows.forEach(row => {
      row.dataset.trackerHistorySelectable = '1';
      row.tabIndex = 0;

      row.addEventListener('click', event => {
        /*
         * Do not interfere with View/Edit links
         * or individual Copy buttons.
         */
        if (
          event.target.closest(
            'a, button, input, select, textarea'
          )
        ) {
          return;
        }

        selectRow(row);
      });

      row.addEventListener('keydown', event => {
        if (
          event.target !== row ||
          !['Enter', ' '].includes(event.key)
        ) {
          return;
        }

        event.preventDefault();
        selectRow(row);
      });
    });

    /*
     * Clear selection whenever pagination changes.
     */
    table.addEventListener(
      'tracker:history-page-changed',
      clearSelection
    );

    /*
     * Clear selection after search filtering.
     */
    const search = document.getElementById(
      'tracker-history-search'
    );

    if (search) {
      search.addEventListener(
        'input',
        () => queueMicrotask(clearSelection)
      );
    }

    /*
     * Integrate with Stage 34.16 individual
     * Previous/Next navigation.
     */
    const previous = document.getElementById(
      'tracker-history-previous'
    );

    const next = document.getElementById(
      'tracker-history-next'
    );

    function selectFocusedRow() {
      window.setTimeout(() => {
        const focused = document.activeElement;

        if (
          focused &&
          focused.matches(
            '#tracker-history-table tbody tr'
          )
        ) {
          selectRow(focused);
        }
      }, 50);
    }

    if (previous) {
      previous.addEventListener(
        'click',
        selectFocusedRow
      );
    }

    if (next) {
      next.addEventListener(
        'click',
        selectFocusedRow
      );
    }
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
