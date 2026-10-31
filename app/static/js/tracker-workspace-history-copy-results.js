/*
 * Tracker Stage 34.9
 * Copy filtered administration history.
 *
 * Browser-only, read-only functionality.
 */
(() => {
  'use strict';

  function initialize() {
    const controls = document.getElementById(
      'tracker-history-controls'
    );

    const table = document.getElementById(
      'tracker-history-table'
    );

    const search = document.getElementById(
      'tracker-history-search'
    );

    if (!controls || !table) return;

    if (document.getElementById(
      'tracker-history-copy-results'
    )) return;

    const button = document.createElement('button');
    button.type = 'button';
    button.id = 'tracker-history-copy-results';
    button.textContent = 'Copy Results';

    const status = document.createElement('span');
    status.id = 'tracker-history-copy-results-status';
    status.setAttribute('role', 'status');
    status.setAttribute('aria-live', 'polite');

    controls.append(button, status);

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

      if (!cell) return '';

      return cell.textContent
        .replace(/\s+/g, ' ')
        .trim();
    }

    function clean(value) {
      return String(value)
        .replace(/[\t\r\n]+/g, ' ')
        .trim();
    }

    function spreadsheetSafe(value) {
      const text = clean(value);

      /*
       * Prevent copied values from being interpreted
       * as formulas in spreadsheet applications.
       */
      if (/^[\s\u0000-\u001f]*[=+\-@]/.test(text)) {
        return "'" + text;
      }

      return text;
    }

    function formatRows(rows) {
      const output = [
        [
          'When',
          'Compound',
          'Amount',
          'Injection site'
        ]
      ];

      for (const row of rows) {
        output.push([
          cellText(row, 0),
          cellText(row, 1),
          cellText(row, 2),
          cellText(row, 3)
        ]);
      }

      return output.map(
        values => values.map(spreadsheetSafe).join('\t')
      ).join('\n');
    }

    async function copy(text) {
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

      const previousFocus = document.activeElement;

      try {
        textarea.focus();
        textarea.select();

        if (!document.execCommand('copy')) {
          throw new Error('Clipboard unavailable');
        }
      } finally {
        textarea.remove();

        if (
          previousFocus &&
          typeof previousFocus.focus === 'function'
        ) {
          previousFocus.focus();
        }
      }
    }

    function updateButton() {
      const count = visibleRows().length;

      button.disabled = count === 0;

      button.title = count
        ? `Copy ${count} displayed administrations`
        : 'No administrations to copy';
    }

    button.addEventListener('click', async () => {
      const rows = visibleRows();

      if (!rows.length) {
        status.textContent = 'No matching administrations.';
        updateButton();
        return;
      }

      button.disabled = true;

      try {
        await copy(formatRows(rows));

        status.textContent =
          `Copied ${rows.length} administrations.`;

        button.textContent = 'Copied ✓';

        window.setTimeout(() => {
          button.textContent = 'Copy Results';
          updateButton();
        }, 2000);
      } catch (error) {
        status.textContent =
          'Clipboard access failed. Check browser permissions.';

        button.textContent = 'Copy failed';

        window.setTimeout(() => {
          button.textContent = 'Copy Results';
          updateButton();
        }, 3000);
      }
    });

    if (search) {
      search.addEventListener('input', () => {
        queueMicrotask(updateButton);
      });
    }

    const clear = document.getElementById(
      'tracker-history-clear'
    );

    if (clear) {
      clear.addEventListener('click', () => {
        queueMicrotask(updateButton);
      });
    }

    updateButton();
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
