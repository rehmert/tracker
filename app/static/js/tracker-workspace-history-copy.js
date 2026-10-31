/*
 * Tracker Stage 34.8
 * Recent Administration Quick Copy
 *
 * Read-only frontend enhancement.
 */

(() => {
  'use strict';

  function initialize() {
    const table = document.getElementById(
      'tracker-history-table'
    );

    if (!table) return;

    const rows = Array.from(
      table.querySelectorAll('tbody tr')
    ).filter(row => row.cells.length >= 5);

    if (!rows.length) return;

    const style = document.createElement('style');

    style.textContent = `
      #tracker-history-table
      .tracker-history-copy {
        margin-left:.5rem;
        padding:.3rem .55rem;
        font-size:.85rem;
        cursor:pointer;
      }

      #tracker-history-table
      .tracker-history-copy:disabled {
        opacity:.6;
        cursor:default;
      }

      #tracker-history-copy-status {
        display:block;
        margin-top:.5rem;
        font-size:.85rem;
        opacity:.8;
      }
    `;

    document.head.appendChild(style);

    const status = document.createElement('span');
    status.id = 'tracker-history-copy-status';
    status.setAttribute('role', 'status');
    status.setAttribute('aria-live', 'polite');

    const section = document.getElementById(
      'tracker-history-section'
    );

    if (section) {
      section.appendChild(status);
    }

    function cellText(row, index) {
      const cell = row.cells[index];

      return cell
        ? cell.textContent.replace(/\s+/g, ' ').trim()
        : '';
    }

    function formatAdministration(row) {
      return [
        `Date: ${cellText(row, 0)}`,
        `Compound: ${cellText(row, 1)}`,
        `Amount: ${cellText(row, 2)}`,
        `Injection site: ${cellText(row, 3)}`
      ].join('\n');
    }

    async function copyText(text) {
      /*
       * Clipboard API is available in secure contexts
       * (HTTPS and localhost).
       */
      if (
        navigator.clipboard &&
        window.isSecureContext
      ) {
        await navigator.clipboard.writeText(text);
        return;
      }

      /*
       * Fallback for HTTP deployments.
       * Uses a temporary textarea without changing
       * the application's forms or selected records.
       */
      const textarea = document.createElement(
        'textarea'
      );

      textarea.value = text;
      textarea.setAttribute('readonly', '');
      textarea.style.position = 'fixed';
      textarea.style.left = '-9999px';
      textarea.style.top = '0';

      document.body.appendChild(textarea);

      const previousFocus = document.activeElement;

      try {
        textarea.focus();
        textarea.select();

        if (!document.execCommand('copy')) {
          throw new Error(
            'Clipboard copy was not permitted.'
          );
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

    rows.forEach(row => {
      const actionCell = row.cells[
        row.cells.length - 1
      ];

      if (!actionCell) return;

      const editLink = actionCell.querySelector(
        'a[href*="/edit"]'
      );

      if (!editLink) return;

      const button = document.createElement('button');

      button.type = 'button';
      button.className = 'tracker-history-copy';
      button.textContent = 'Copy';

      const description = [
        cellText(row, 0),
        cellText(row, 1)
      ].filter(Boolean).join(', ');

      button.setAttribute(
        'aria-label',
        `Copy administration: ${description}`
      );

      button.addEventListener('click', async () => {
        button.disabled = true;

        try {
          await copyText(
            formatAdministration(row)
          );

          button.textContent = 'Copied ✓';

          status.textContent =
            `Copied administration: ${description}`;

          window.setTimeout(() => {
            button.textContent = 'Copy';
          }, 2000);
        } catch (error) {
          button.textContent = 'Copy failed';

          status.textContent =
            'Clipboard access failed. ' +
            'Check browser clipboard permissions.';

          window.setTimeout(() => {
            button.textContent = 'Copy';
          }, 3000);
        } finally {
          button.disabled = false;
        }
      });

      actionCell.appendChild(button);
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
