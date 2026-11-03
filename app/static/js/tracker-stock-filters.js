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

    const count = toolbar.querySelector(
      '[data-stock-visible-count]'
    );

    const empty = document.querySelector(
      '[data-stock-filter-empty]'
    );

    if (!search || !status || !reset ||
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
