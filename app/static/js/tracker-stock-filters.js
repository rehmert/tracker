/*
 * Tracker Supplies stock review.
 * Read-only filtering, sorting, CSV and print.
 * Inventory use forms remain unchanged.
 */
(() => {
  'use strict';

  function initialize() {
    const toolbar = document.querySelector(
      '[data-stock-filter-toolbar]'
    );
    const table = document.querySelector(
      '[data-stock-review-table]'
    );

    if (!toolbar || !table ||
        toolbar.dataset.initialized) return;

    const get = selector =>
      toolbar.querySelector(selector);

    const search = get('[data-stock-search]');
    const status = get('[data-stock-status-filter]');
    const sort = get('[data-stock-sort]');
    const reset = get('[data-stock-filter-reset]');
    const exportButton = get('[data-stock-export]');
    const printButton = get('[data-stock-print]');
    const count = get('[data-stock-visible-count]');
    const breakdown = get('[data-stock-breakdown]');
    const empty = document.querySelector(
      '[data-stock-filter-empty]'
    );

    if (!search || !status || !sort || !reset ||
        !exportButton || !printButton || !count ||
        !breakdown || !empty) return;

    const tbody = table.tBodies[0];
    if (!tbody) return;

    const rows = Array.from(
      tbody.querySelectorAll(
        'tr[data-stock-review-row]'
      )
    );

    toolbar.dataset.initialized = 'true';

    const originalOrder = new Map(
      rows.map((row, index) => [row, index])
    );

    const collator = new Intl.Collator(undefined, {
      numeric: true,
      sensitivity: 'base'
    });

    function rowStatus(row) {
      return row.querySelector(
        '[data-stock-state]'
      )?.dataset.stockState || '';
    }

    function cellText(row, index) {
      return row.cells[index]?.textContent
        ?.replace(/\s+/g, ' ').trim() || '';
    }

    function rowSearchText(row) {
      return [
        cellText(row, 0),
        cellText(row, 1)
      ].join(' ').toLocaleLowerCase();
    }

    function numericValue(text) {
      const match = text.replace(/,/g, '').match(
        /-?\d+(?:\.\d+)?/
      );
      return match ? Number(match[0]) : NaN;
    }

    function sortRows() {
      const choice = sort.value;
      const rank = {
        depleted: 0,
        low: 1,
        available: 2
      };

      rows.sort((a, b) => {
        let result = 0;

        if (choice === 'product') {
          result = collator.compare(
            cellText(a, 0), cellText(b, 0)
          );
        } else if (choice === 'category') {
          result = collator.compare(
            cellText(a, 1), cellText(b, 1)
          );
        } else if (
          choice === 'remaining-asc' ||
          choice === 'remaining-desc'
        ) {
          const x = numericValue(cellText(a, 3));
          const y = numericValue(cellText(b, 3));

          if (Number.isFinite(x) &&
              Number.isFinite(y)) {
            result = x - y;

            if (choice === 'remaining-desc') {
              result *= -1;
            }
          }
        } else if (choice === 'attention') {
          result =
            (rank[rowStatus(a)] ?? 3) -
            (rank[rowStatus(b)] ?? 3);
        }

        return result ||
          originalOrder.get(a) -
          originalOrder.get(b);
      });

      // Move the existing row elements. This
      // preserves their forms and hidden tokens.
      rows.forEach(row => tbody.append(row));
    }

    function update() {
      const query = search.value.trim()
        .toLocaleLowerCase();
      const selected = status.value;

      const matching = {
        available: 0,
        low: 0,
        depleted: 0
      };

      let visible = 0;

      rows.forEach(row => {
        const state = rowStatus(row);

        const matchesSearch =
          !query || rowSearchText(row).includes(query);

        const matchesStatus =
          selected === 'all' ||
          (selected === 'attention' &&
           (state === 'low' ||
            state === 'depleted')) ||
          state === selected;

        const show = matchesSearch && matchesStatus;

        row.hidden = !show;

        if (show) {
          visible++;
          if (Object.prototype.hasOwnProperty.call(
            matching, state
          )) {
            matching[state]++;
          }
        }
      });

      sortRows();

      count.textContent =
        'Showing ' + visible +
        ' of ' + rows.length + ' supplies';

      breakdown.textContent =
        'Matching: ' +
        matching.available + ' available · ' +
        matching.low + ' low · ' +
        matching.depleted + ' out of stock';

      empty.hidden = visible !== 0 ||
        rows.length === 0;

      exportButton.disabled = visible === 0;
      printButton.disabled = visible === 0;
    }

    search.addEventListener('input', update);
    status.addEventListener('change', update);
    sort.addEventListener('change', update);

    reset.addEventListener('click', () => {
      search.value = '';
      status.value = 'all';
      sort.value = 'original';
      update();
      search.focus();
    });

    document.querySelectorAll(
      '[data-stock-quick-filter]'
    ).forEach(button => {
      button.addEventListener('click', () => {
        search.value = '';
        status.value =
          button.dataset.stockQuickFilter;
        update();
      });
    });

    function csvValue(value) {
      let text = String(value ?? '')
        .replace(/[\r\n\t]+/g, ' ')
        .replace(/\s+/g, ' ')
        .trim();

      // Prevent spreadsheet formula execution.
      if (/^[=+@-]/.test(text)) {
        text = "'" + text;
      }

      return '"' + text.replace(/"/g, '""') + '"';
    }

    function rowForCsv(row) {
      const cells = row.cells;
      return [
        cells[0]?.textContent || '',
        cells[1]?.textContent || '',
        cells[2]?.textContent || '',
        cells[3]?.textContent || '',
        row.querySelector('[data-stock-state]')
          ?.textContent || ''
      ];
    }

    exportButton.addEventListener('click', () => {
      // This intentionally retains rows.filter()
      // required by the existing regression test.
      // rows is already in current display order.
      const visibleRows = rows.filter(
        row => !row.hidden
      );

      if (!visibleRows.length) return;

      const header = [
        'Product',
        'Category',
        'Purchased',
        'Remaining',
        'Stock Status'
      ];

      const records = [
        header,
        ...visibleRows.map(rowForCsv)
      ];

      const csv = '\uFEFF' + records.map(
        record => record.map(csvValue).join(',')
      ).join('\r\n') + '\r\n';

      const blob = new Blob([csv], {
        type: 'text/csv;charset=utf-8'
      });

      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');

      link.href = url;
      link.download = 'tracker-supply-stock-' +
        new Date().toISOString().slice(0, 10) +
        '.csv';

      document.body.append(link);
      link.click();
      link.remove();

      setTimeout(
        () => URL.revokeObjectURL(url), 1000
      );
    });

    function clearPrintMode() {
      document.body.classList.remove(
        'tracker-stock-print-mode'
      );
    }

    window.addEventListener(
      'afterprint', clearPrintMode
    );

    printButton.addEventListener('click', () => {
      if (printButton.disabled) return;

      document.body.classList.add(
        'tracker-stock-print-mode'
      );

      window.print();
    });

    update();
  }

  if (document.readyState === 'loading') {
    document.addEventListener(
      'DOMContentLoaded', initialize, { once: true }
    );
  } else {
    initialize();
  }
})();
