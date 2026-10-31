/*
 * Tracker Stage 34.18
 * Selected Administration Quick Actions
 *
 * Frontend-only.
 * Uses existing administration links and records.
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

    const panel = document.getElementById(
      'tracker-history-selection'
    );

    const details = document.getElementById(
      'tracker-history-selection-details'
    );

    if (!section || !table || !panel || !details) {
      return;
    }

    if (document.getElementById(
      'tracker-history-quick-actions'
    )) {
      return;
    }

    const style = document.createElement('style');

    style.textContent = `
      #tracker-history-quick-actions {
        display:flex;
        align-items:center;
        flex-wrap:wrap;
        gap:.45rem;
        margin-top:.65rem;
      }

      #tracker-history-quick-actions button,
      #tracker-history-quick-actions a {
        display:inline-flex;
        align-items:center;
        justify-content:center;
        padding:.35rem .65rem;
        border:1px solid var(--border,#ccc);
        border-radius:.4rem;
        background:transparent;
        color:inherit;
        font:inherit;
        text-decoration:none;
        cursor:pointer;
      }

      #tracker-history-quick-actions button:disabled {
        opacity:.4;
        cursor:default;
      }

      #tracker-history-quick-actions button:focus-visible,
      #tracker-history-quick-actions a:focus-visible {
        outline:2px solid var(--accent,#2563eb);
        outline-offset:2px;
      }

      #tracker-history-quick-position {
        font-size:.85rem;
        opacity:.8;
      }

      #tracker-history-quick-status {
        display:block;
        margin-top:.4rem;
        font-size:.85rem;
      }
    `;

    document.head.appendChild(style);

    const actions = document.createElement('div');
    actions.id = 'tracker-history-quick-actions';

    function button(id, label) {
      const element = document.createElement('button');
      element.type = 'button';
      element.id = id;
      element.textContent = label;
      return element;
    }

    const previous = button(
      'tracker-history-quick-previous',
      '← Previous'
    );

    const next = button(
      'tracker-history-quick-next',
      'Next →'
    );

    const copy = button(
      'tracker-history-quick-copy',
      'Copy Details'
    );

    const edit = document.createElement('a');
    edit.id = 'tracker-history-quick-edit';
    edit.textContent = 'View / Edit';

    const position = document.createElement('span');
    position.id = 'tracker-history-quick-position';

    const status = document.createElement('span');
    status.id = 'tracker-history-quick-status';
    status.setAttribute('role', 'status');
    status.setAttribute('aria-live', 'polite');

    actions.append(
      previous,
      next,
      edit,
      copy,
      position
    );

    const content = details.parentElement;

    content.append(actions, status);

    let selected = null;

    function visibleRows() {
      return Array.from(
        table.querySelectorAll('tbody tr')
      ).filter(row =>
        !row.hidden &&
        getComputedStyle(row).display !== 'none'
      );
    }

    function selectedRow() {
      const row = table.querySelector(
        'tbody tr.tracker-history-selected'
      );

      return row && visibleRows().includes(row)
        ? row
        : null;
    }

    function cellText(row, index) {
      const cell = row.cells[index];

      return cell
        ? cell.textContent.replace(/\s+/g, ' ').trim()
        : '';
    }

    function update() {
      selected = selectedRow();

      const rows = visibleRows();
      const index = selected
        ? rows.indexOf(selected)
        : -1;

      previous.disabled = index <= 0;
      next.disabled =
        index < 0 || index >= rows.length - 1;

      copy.disabled = !selected;

      const editLink = selected
        ? selected.querySelector(
            'a[href*="/edit"]'
          )
        : null;

      if (editLink) {
        edit.href = editLink.href;
        edit.hidden = false;
      } else {
        edit.removeAttribute('href');
        edit.hidden = true;
      }

      position.textContent = selected
        ? `${index + 1} of ${rows.length} displayed`
        : 'No administration selected';
    }

    function selectRow(row) {
      if (!row) return;

      /*
       * Reuse the existing Stage 34.17
       * selection handler.
       */
      row.click();

      row.focus({ preventScroll:true });

      row.scrollIntoView({
        behavior:'smooth',
        block:'nearest'
      });

      update();
    }

    function navigate(direction) {
      const rows = visibleRows();

      if (!rows.length) return;

      const index = selected
        ? rows.indexOf(selected)
        : -1;

      const target = index < 0
        ? (direction > 0 ? 0 : rows.length - 1)
        : Math.max(
            0,
            Math.min(
              rows.length - 1,
              index + direction
            )
          );

      selectRow(rows[target]);
    }

    previous.addEventListener('click', () => {
      navigate(-1);
    });

    next.addEventListener('click', () => {
      navigate(1);
    });

    async function copyText(text) {
      if (
        navigator.clipboard &&
        window.isSecureContext
      ) {
        await navigator.clipboard.writeText(text);
        return;
      }

      const textarea = document.createElement('textarea');

      textarea.value = text;
      textarea.readOnly = true;
      textarea.style.position = 'fixed';
      textarea.style.left = '-9999px';

      document.body.appendChild(textarea);

      try {
        textarea.select();

        if (!document.execCommand('copy')) {
          throw new Error('Clipboard unavailable');
        }
      } finally {
        textarea.remove();
      }
    }

    copy.addEventListener('click', async () => {
      if (!selected) return;

      const text = [
        `Date: ${cellText(selected, 0)}`,
        `Compound: ${cellText(selected, 1)}`,
        `Amount: ${cellText(selected, 2)}`,
        `Injection site: ${cellText(selected, 3)}`
      ].join('\n');

      try {
        await copyText(text);
        status.textContent =
          'Selected administration copied.';
      } catch (_) {
        status.textContent =
          'Clipboard access failed.';
      }
    });

    /*
     * Update after Stage 34.17 handles row clicks.
     */
    table.addEventListener('click', event => {
      if (event.target.closest('tbody tr')) {
        queueMicrotask(update);
      }
    });

    const clear = document.getElementById(
      'tracker-history-selection-clear'
    );

    if (clear) {
      clear.addEventListener('click', () => {
        queueMicrotask(update);
      });
    }

    table.addEventListener(
      'tracker:history-page-changed',
      () => queueMicrotask(update)
    );

    const search = document.getElementById(
      'tracker-history-search'
    );

    if (search) {
      search.addEventListener(
        'input',
        () => queueMicrotask(update)
      );
    }

    /*
     * Alt+Up and Alt+Down navigate the visible
     * administrations when focus is inside the
     * Recent Administrations section.
     */
    section.addEventListener('keydown', event => {
      if (!event.altKey || event.ctrlKey || event.metaKey) {
        return;
      }

      if (event.key === 'ArrowUp') {
        event.preventDefault();
        navigate(-1);
      } else if (event.key === 'ArrowDown') {
        event.preventDefault();
        navigate(1);
      }
    });

    update();
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
