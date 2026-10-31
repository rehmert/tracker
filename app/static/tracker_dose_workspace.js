/*
 * Tracker Stage 28
 * Read-only browser sorting and vial search.
 */

(() => {
  'use strict';

  function init() {
    const input = document.getElementById('tracker-vial-search');
    const container = document.getElementById('tracker-available-vials');

    if (!input || !container) return;

    const table = container.querySelector(
      '[data-tracker-sortable-vials]'
    );

    if (!table) return;

    const tbody = table.querySelector('tbody');

    const rows = Array.from(
      tbody.querySelectorAll('[data-tracker-vial-row]')
    );

    const headers = Array.from(
      table.querySelectorAll('[data-tracker-sort-key]')
    );

    const count = document.getElementById('tracker-vial-count');
    const empty = document.getElementById('tracker-vial-no-matches');
    const clear = document.getElementById('tracker-vial-clear');
    const reset = document.getElementById('tracker-vial-reset');

    let sortKey = 'recommended';
    let direction = 'asc';

    function getValue(row, key) {
      const property = key.replace(
        /-([a-z])/g,
        (_, letter) => letter.toUpperCase()
      );

      return row.dataset[property] || '';
    }

    function compare(a, b) {
      if (sortKey === 'recommended') {
        const av = Number(getValue(a, 'recommended'));
        const bv = Number(getValue(b, 'recommended'));

        if (av !== bv) return bv - av;
      } else if (sortKey === 'remaining') {
        const av = Number(getValue(a, 'remaining'));
        const bv = Number(getValue(b, 'remaining'));

        if (av !== bv) {
          return direction === 'asc'
            ? av - bv
            : bv - av;
        }
      } else {
        const av = getValue(a, sortKey);
        const bv = getValue(b, sortKey);

        const dateKey = [
          'first-used',
          'beyond-use',
          'expires'
        ].includes(sortKey);

        if (dateKey && !av && bv) return 1;
        if (dateKey && av && !bv) return -1;

        const result = av.localeCompare(
          bv,
          undefined,
          { numeric: true, sensitivity: 'base' }
        );

        if (result !== 0) {
          return direction === 'asc'
            ? result
            : -result;
        }
      }

      return Number(getValue(a, 'id')) -
             Number(getValue(b, 'id'));
    }

    function sortRows() {
      rows.sort(compare);

      const fragment = document.createDocumentFragment();

      rows.forEach(row => fragment.appendChild(row));

      tbody.appendChild(fragment);

      headers.forEach(header => {
        const active =
          header.dataset.trackerSortKey === sortKey;

        header.setAttribute(
          'aria-sort',
          active
            ? (direction === 'asc'
                ? 'ascending'
                : 'descending')
            : 'none'
        );
      });
    }

    function update() {
      const query = input.value.trim().toLocaleLowerCase();
      let visible = 0;

      rows.forEach(row => {
        const match =
          !query ||
          row.textContent.toLocaleLowerCase().includes(query);

        row.hidden = !match;

        if (match) visible++;
      });

      if (count) {
        count.textContent =
          `${visible} of ${rows.length} vials shown`;
      }

      if (empty) empty.hidden = visible !== 0;
      if (clear) clear.hidden = !query;
    }

    function resetSearch() {
      input.value = '';
      update();
      input.focus();
    }

    headers.forEach(header => {
      const button = header.querySelector('button');

      if (!button) return;

      button.addEventListener('click', () => {
        const key = header.dataset.trackerSortKey;

        if (sortKey === key) {
          direction =
            direction === 'asc' ? 'desc' : 'asc';
        } else {
          sortKey = key;
          direction = 'asc';
        }

        sortRows();
        update();
      });
    });

    input.addEventListener('input', update);

    if (clear) clear.addEventListener('click', resetSearch);
    if (reset) reset.addEventListener('click', resetSearch);

    sortRows();
    update();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
