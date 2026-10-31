/*
 * Tracker Stage 34.19
 * Administration History Keyboard Navigation
 *
 * Frontend-only.
 * Preserves existing selection and quick actions.
 */

(() => {
  'use strict';

  function initialize() {
    const section = document.getElementById(
      'tracker-history-section'
    );

    const table = document.getElementById(
      'tracker-history-table'
    );

    const clear = document.getElementById(
      'tracker-history-selection-clear'
    );

    if (!section || !table || !clear) return;

    if (document.getElementById(
      'tracker-history-keyboard-status'
    )) {
      return;
    }

    const rows = Array.from(
      table.querySelectorAll('tbody tr')
    ).filter(row => row.cells.length >= 4);

    if (!rows.length) return;

    const style = document.createElement('style');

    style.textContent = `
      #tracker-history-table tbody tr:focus-visible {
        outline:3px solid var(--accent,#2563eb);
        outline-offset:-3px;
      }

      #tracker-history-table
      tbody tr.tracker-history-selected {
        box-shadow:inset 4px 0 0
          var(--accent,#2563eb);
      }

      #tracker-history-keyboard-help {
        margin:.5rem 0;
        font-size:.82rem;
        opacity:.75;
      }

      #tracker-history-keyboard-status {
        position:absolute;
        width:1px;
        height:1px;
        padding:0;
        margin:-1px;
        overflow:hidden;
        clip:rect(0,0,0,0);
        white-space:nowrap;
        border:0;
      }
    `;

    document.head.appendChild(style);

    const help = document.createElement('p');
    help.id = 'tracker-history-keyboard-help';

    help.textContent =
      'Keyboard: ↑/↓ move between rows · ' +
      'Home/End jump · Enter selects · ' +
      'Escape clears selection.';

    const status = document.createElement('div');
    status.id = 'tracker-history-keyboard-status';
    status.setAttribute('role', 'status');
    status.setAttribute('aria-live', 'polite');
    status.setAttribute('aria-atomic', 'true');

    const scroll = table.closest('.scroll');

    if (scroll) {
      scroll.insertAdjacentElement(
        'beforebegin',
        help
      );
    } else {
      table.insertAdjacentElement(
        'beforebegin',
        help
      );
    }

    section.appendChild(status);

    function visibleRows() {
      return Array.from(
        table.querySelectorAll('tbody tr')
      ).filter(row =>
        !row.hidden &&
        getComputedStyle(row).display !== 'none'
      );
    }

    function cellText(row, index) {
      const cell = row.cells[index];

      return cell
        ? cell.textContent.replace(/\s+/g, ' ').trim()
        : '';
    }

    function announce(row) {
      const visible = visibleRows();
      const index = visible.indexOf(row);

      if (index < 0) return;

      status.textContent =
        `${cellText(row, 1)}, ` +
        `${cellText(row, 2)}, ` +
        `${cellText(row, 0)}. ` +
        `Administration ${index + 1} of ${visible.length}.`;
    }

    function focusRow(row) {
      if (!row) return;

      row.focus({
        preventScroll:true
      });

      row.scrollIntoView({
        behavior:'smooth',
        block:'nearest'
      });

      announce(row);
    }

    function move(current, direction) {
      const visible = visibleRows();

      if (!visible.length) return;

      const index = visible.indexOf(current);

      const target = index < 0
        ? (direction > 0 ? 0 : visible.length - 1)
        : Math.max(
            0,
            Math.min(
              visible.length - 1,
              index + direction
            )
          );

      focusRow(visible[target]);
    }

    /*
     * Handle navigation only when a history row
     * itself has keyboard focus.
     *
     * Do not intercept typing or native controls.
     */
    table.addEventListener('keydown', event => {
      const row = event.target.closest(
        'tbody tr[data-tracker-history-selectable]'
      );

      if (!row || event.target !== row) return;

      if (
        event.altKey ||
        event.ctrlKey ||
        event.metaKey
      ) {
        return;
      }

      const visible = visibleRows();

      switch (event.key) {
        case 'ArrowUp':
          event.preventDefault();
          move(row, -1);
          break;

        case 'ArrowDown':
          event.preventDefault();
          move(row, 1);
          break;

        case 'Home':
          event.preventDefault();
          focusRow(visible[0]);
          break;

        case 'End':
          event.preventDefault();
          focusRow(visible[visible.length - 1]);
          break;

        case 'Escape':
          event.preventDefault();
          clear.click();
          status.textContent =
            'Administration selection cleared.';
          break;

        case 'Enter':
          /*
           * Stage 34.17 already handles Enter.
           * Announce the selection after its handler.
           */
          queueMicrotask(() => announce(row));
          break;
      }
    });

    /*
     * Escape also clears selection when focus
     * is elsewhere inside the history section,
     * excluding editable controls.
     */
    section.addEventListener('keydown', event => {
      if (event.key !== 'Escape') return;

      const target = event.target;

      if (
        target.matches(
          'input, textarea, select, [contenteditable="true"]'
        )
      ) {
        return;
      }

      if (target.closest(
        '#tracker-history-table tbody tr'
      )) {
        return;
      }

      if (clear.disabled) return;

      event.preventDefault();
      clear.click();

      status.textContent =
        'Administration selection cleared.';
    });

    /*
     * Announce selection made with the mouse
     * or existing Quick Actions buttons.
     */
    table.addEventListener('click', event => {
      const row = event.target.closest('tbody tr');

      if (!row) return;

      queueMicrotask(() => {
        if (row.classList.contains(
          'tracker-history-selected'
        )) {
          announce(row);
        }
      });
    });

    /*
     * Avoid leaving keyboard focus on a hidden
     * row when pagination changes.
     */
    table.addEventListener(
      'tracker:history-page-changed',
      () => {
        const active = document.activeElement;

        if (
          active &&
          table.contains(active) &&
          active.closest('tbody tr') &&
          !visibleRows().includes(
            active.closest('tbody tr')
          )
        ) {
          const first = visibleRows()[0];

          if (first) {
            focusRow(first);
          } else {
            clear.focus();
          }
        }
      }
    );
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
