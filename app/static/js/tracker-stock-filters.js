/*
 * Tracker Supplies stock review.
 *
 * Read-only table filtering. Existing supply-use
 * forms and submission tokens remain in the DOM.
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

    const search = toolbar.querySelector(
      '[data-stock-search]'
    );

    const status = toolbar.querySelector(
      '[data-stock-status-filter]'
    );

    const reset = toolbar.querySelector(
      '[data-stock-filter-reset]'
    );

    const exportButton = toolbar.querySelector(
      '[data-stock-export]'
    );

    const printButton = toolbar.querySelector(
      '[data-stock-print]'
    );

    const count = toolbar.querySelector(
      '[data-stock-visible-count]'
    );

    const empty = document.querySelector(
      '[data-stock-filter-empty]'
    );

    if (!search || !status || !reset ||
        !exportButton || !printButton ||
        !count || !empty) return;

    const rows = Array.from(
      table.querySelectorAll(
        'tbody tr[data-stock-review-row]'
      )
    );

    toolbar.dataset.initialized = 'true';

    function rowStatus(row) {
      return row.querySelector(
        '[data-stock-state]'
      )?.dataset.stockState || '';
    }

    function rowSearchText(row) {
      // Search product and inventory category.
      // Never include form inputs or submission tokens.
      return [
        row.cells[0]?.textContent || '',
        row.cells[1]?.textContent || ''
      ].join(' ').toLocaleLowerCase();
    }

    function update() {
      const query = search.value
        .trim()
        .toLocaleLowerCase();

      const selected = status.value;

      let visible = 0;

      rows.forEach(row => {
        const stockState = rowStatus(row);

        const matchesSearch =
          !query || rowSearchText(row).includes(query);

        const matchesStatus =
          selected === 'all' ||
          (selected === 'attention' &&
           (stockState === 'low' ||
            stockState === 'depleted')) ||
          stockState === selected;

        const show =
          matchesSearch && matchesStatus;

        row.hidden = !show;

        if (show) visible++;
      });

      count.textContent =
        'Showing ' + visible +
        ' of ' + rows.length + ' supplies';

      empty.hidden =
        visible !== 0 || rows.length === 0;

      exportButton.disabled = visible === 0;
      printButton.disabled = visible === 0;
    }

    search.addEventListener('input', update);
    status.addEventListener('change', update);

    reset.addEventListener('click', () => {
      search.value = '';
      status.value = 'all';
      update();
      search.focus();
    });

    // Explicit quick-filter buttons reuse the
    // exact same filtering logic.
    document.querySelectorAll(
      '[data-stock-quick-filter]'
    ).forEach(button => {
      button.addEventListener('click', () => {
        search.value = '';
        status.value =
          button.dataset.stockQuickFilter;
        update();
        document.querySelector(
          '[data-stock-filter-toolbar]'
        )?.scrollIntoView({
          block: 'nearest',
          behavior: 'instant'
        });
      });
    });


    function csvValue(value) {
      // Quote all CSV values and neutralize
      // spreadsheet formula interpretation.
      let text = String(value ?? '')
        .replace(/\\s+/g, ' ')
        .trim();

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

      const csv = '\\uFEFF' + records.map(
        record => record.map(csvValue).join(',')
      ).join('\\r\\n') + '\\r\\n';

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

      // Revoke only after browser download has
      // been initiated.
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    });

    printButton.addEventListener('click', () => {
      window.print();
    });

    update();
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
