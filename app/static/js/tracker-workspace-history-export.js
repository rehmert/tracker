/*
 * Tracker Stage 34.7
 * Recent Administrations CSV Export
 *
 * Browser-only export of currently visible rows.
 * No network requests or database modifications.
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
      'tracker-history-export'
    )) return;

    const button = document.createElement('button');

    button.type = 'button';
    button.id = 'tracker-history-export';
    button.textContent = 'Export CSV';
    button.title =
      'Export administrations currently shown in this table';

    const status = document.createElement('span');

    status.id = 'tracker-history-export-status';
    status.setAttribute('role', 'status');
    status.setAttribute('aria-live', 'polite');

    controls.append(button, status);

    function visibleRows() {
      return Array.from(
        table.querySelectorAll('tbody tr')
      ).filter(row => {
        return !row.hidden &&
          getComputedStyle(row).display !== 'none';
      });
    }

    function cellText(row, index) {
      const cell = row.cells[index];

      return cell
        ? cell.textContent
            .replace(/\s+/g, ' ')
            .trim()
        : '';
    }

    function csvCell(value) {
      let text = String(value ?? '');

      /*
       * Prevent spreadsheet formula execution when
       * exported values are opened in Excel or Sheets.
       * Preserve ordinary numbers and dates.
       */
      if (/^[\s\u0000-\u001f]*[=+\-@\t\r]/.test(text)) {
        text = "'" + text;
      }

      return '"' +
        text.replace(/"/g, '""') +
        '"';
    }

    function makeCSV(rows) {
      const output = [
        [
          'When',
          'Compound',
          'Amount',
          'Injection site'
        ]
      ];

      rows.forEach(row => {
        output.push([
          cellText(row, 0),
          cellText(row, 1),
          cellText(row, 2),
          cellText(row, 3)
        ]);
      });

      return output
        .map(cells => cells.map(csvCell).join(','))
        .join('\r\n') + '\r\n';
    }

    function updateButton() {
      const count = visibleRows().length;

      button.disabled = count === 0;

      button.title = count
        ? `Export ${count} displayed administrations`
        : 'No displayed administrations to export';
    }

    button.addEventListener('click', () => {
      const rows = visibleRows();

      if (!rows.length) {
        status.textContent =
          'No administrations to export.';
        updateButton();
        return;
      }

      const csv = makeCSV(rows);

      const blob = new Blob(
        ['\uFEFF', csv],
        {
          type:'text/csv;charset=utf-8'
        }
      );

      const url = URL.createObjectURL(blob);

      const link = document.createElement('a');

      const date = new Date();
      const year = date.getFullYear();
      const month = String(
        date.getMonth() + 1
      ).padStart(2, '0');

      const day = String(
        date.getDate()
      ).padStart(2, '0');

      link.href = url;
      link.download =
        `tracker-administrations-${year}-${month}-${day}.csv`;

      document.body.appendChild(link);
      link.click();
      link.remove();

      setTimeout(() => {
        URL.revokeObjectURL(url);
      }, 1000);

      status.textContent =
        `Exported ${rows.length} administrations.`;
    });

    /*
     * Stage 34.6 updates row visibility on input.
     * Register afterward so the button reflects
     * the resulting search matches.
     */
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
      { once:true }
    );
  } else {
    initialize();
  }
})();
