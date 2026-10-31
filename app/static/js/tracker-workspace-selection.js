/*
 * Tracker Stage 34.5
 * Dose Workspace vial selection and recording preview.
 *
 * Frontend only.
 * Uses existing server-generated Record dose URLs.
 */

(() => {
  'use strict';

  function init() {
    const container = document.getElementById(
      'tracker-available-vials'
    );

    const panel = document.getElementById(
      'tracker-selected-vial'
    );

    if (!container || !panel) return;

    const table = container.querySelector(
      '[data-tracker-sortable-vials]'
    );

    if (!table) return;

    const rows = Array.from(
      table.querySelectorAll('[data-tracker-vial-row]')
    );

    const compound = document.getElementById(
      'tracker-selected-compound'
    );

    const vial = document.getElementById(
      'tracker-selected-label'
    );

    const concentration = document.getElementById(
      'tracker-selected-concentration'
    );

    const remaining = document.getElementById(
      'tracker-selected-remaining'
    );

    const guidance = document.getElementById(
      'tracker-selected-guidance'
    );

    const action = document.getElementById(
      'tracker-selected-record'
    );

    const clear = document.getElementById(
      'tracker-selected-clear'
    );

    const status = document.getElementById(
      'tracker-selected-status'
    );

    if (!compound || !vial || !concentration ||
        !remaining || !guidance || !action ||
        !clear || !status) {
      return;
    }

    let selected = null;

    const style = document.createElement('style');

    style.textContent = `
      #tracker-selected-vial {
        margin: 1rem 0;
        padding: 1rem 1.2rem;
        border: 1px solid var(--border, #ccc);
        border-radius: .75rem;
      }

      #tracker-selected-vial[hidden] {
        display: none !important;
      }

      #tracker-selected-vial h3 {
        margin: 0 0 .75rem;
      }

      #tracker-selected-vial .tracker-selection-grid {
        display: grid;
        grid-template-columns:
          repeat(auto-fit, minmax(150px, 1fr));
        gap: .8rem 1.2rem;
      }

      #tracker-selected-vial .tracker-selection-field strong {
        display: block;
        font-size: .8rem;
        opacity: .75;
        margin-bottom: .2rem;
      }

      #tracker-selected-vial .tracker-selection-actions {
        display: flex;
        align-items: center;
        flex-wrap: wrap;
        gap: .75rem;
        margin-top: 1rem;
      }

      #tracker-selected-record {
        display: inline-block;
        padding: .65rem 1rem;
        border-radius: .5rem;
        background: var(--accent, #2563eb);
        color: white;
        text-decoration: none;
        font-weight: 600;
      }

      #tracker-selected-record:hover {
        filter: brightness(.92);
      }

      #tracker-selected-clear {
        cursor: pointer;
      }

      #tracker-available-vials
      tr.tracker-workspace-selected {
        outline: 2px solid var(--accent, #2563eb);
        outline-offset: -2px;
      }

      #tracker-available-vials
      tr.tracker-workspace-selected > td {
        box-shadow: inset 0 0 0 9999px
          rgba(59, 130, 246, .10);
      }

      #tracker-available-vials
      tr[data-tracker-vial-row] {
        cursor: pointer;
      }

      #tracker-available-vials
      tr[data-tracker-vial-row]:focus-visible {
        outline: 2px solid var(--accent, #2563eb);
      }
    `;

    document.head.appendChild(style);

    function cellText(row, index) {
      return row.cells[index]
        ? row.cells[index].textContent.trim()
        : '';
    }

    function setText(element, value) {
      element.textContent = value || 'Not recorded';
    }

    function select(row) {
      if (!row || !rows.includes(row)) return;

      const link = row.querySelector(
        'td:last-child a[href^="/doses?"]'
      );

      if (!link) return;

      if (selected) {
        selected.classList.remove(
          'tracker-workspace-selected'
        );
        selected.setAttribute(
          'aria-selected',
          'false'
        );
      }

      selected = row;

      row.classList.add(
        'tracker-workspace-selected'
      );

      row.setAttribute(
        'aria-selected',
        'true'
      );

      setText(compound, cellText(row, 0));
      setText(vial, cellText(row, 1));
      setText(concentration, cellText(row, 3));
      setText(remaining, cellText(row, 4));

      const guidanceCell = row.cells[8];

      guidance.replaceChildren();

      if (guidanceCell) {
        /*
         * Clone the existing guidance, including
         * recommendation and date-warning badges.
         * Never recompute inventory safety rules.
         */
        const clone = guidanceCell.cloneNode(true);

        while (clone.firstChild) {
          guidance.appendChild(clone.firstChild);
        }
      }

      action.href = link.href;

      status.textContent =
        `Selected ${cellText(row, 0)}, ` +
        `${cellText(row, 1)}.`;

      panel.hidden = false;
    }

    function clearSelection() {
      if (selected) {
        selected.classList.remove(
          'tracker-workspace-selected'
        );

        selected.setAttribute(
          'aria-selected',
          'false'
        );
      }

      selected = null;
      panel.hidden = true;
      action.removeAttribute('href');
      status.textContent = 'Selection cleared.';
    }

    rows.forEach(row => {
      row.tabIndex = 0;

      row.setAttribute(
        'aria-selected',
        'false'
      );

      row.addEventListener('click', event => {
        /*
         * Preserve normal links, buttons,
         * form controls and their behavior.
         */
        if (event.target.closest(
          'a,button,input,select,textarea,label'
        )) {
          return;
        }

        select(row);
      });

      row.addEventListener('keydown', event => {
        if (
          event.target !== row ||
          !['Enter', ' '].includes(event.key)
        ) {
          return;
        }

        event.preventDefault();
        select(row);
      });
    });

    clear.addEventListener(
      'click',
      clearSelection
    );

    /*
     * The existing search hides rows rather
     * than removing them. Clear the preview
     * if its selected row becomes hidden.
     */
    const search = document.getElementById(
      'tracker-vial-search'
    );

    if (search) {
      search.addEventListener('input', () => {
        if (selected && selected.hidden) {
          clearSelection();
        }
      });
    }

    /*
     * Sorting moves existing row elements.
     * The selection remains attached to its row.
     */

    const recommended = rows.find(
      row => row.dataset.trackerRecommended === '1'
    );

    if (recommended) {
      select(recommended);
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener(
      'DOMContentLoaded',
      init,
      { once: true }
    );
  } else {
    init();
  }
})();
