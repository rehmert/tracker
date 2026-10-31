/*
 * Tracker: Vials inventory table sorting.
 * Client-side only; no inventory modifications.
 */
(() => {
  'use strict';

  function init() {
    const table = document.getElementById(
      'tracker-vials-sortable'
    );

    if (!table) return;

    const body = table.tBodies[0];

    const headers = [
      ...table.querySelectorAll(
        'thead th[data-vial-sort]'
      )
    ];

    const cells = {
      compound: 1,
      vial: 2,
      remaining: 3,
      amount: 4,
      landed: 5,
      cost: 6,
      coa: 7,
      status: 8
    };

    const numberKeys = new Set([
      'remaining',
      'amount',
      'landed',
      'cost'
    ]);

    const collator = new Intl.Collator(undefined, {
      numeric: true,
      sensitivity: 'base'
    });

    let active = null;
    let descending = false;

    function number(text) {
      const match = text
        .replaceAll(',', '')
        .match(/-?\d+(?:\.\d+)?/);

      return match ? Number(match[0]) : null;
    }

    function compareRows(a, b, key) {
      const av =
        a.cells[cells[key]]?.textContent.trim() || '';

      const bv =
        b.cells[cells[key]]?.textContent.trim() || '';

      if (numberKeys.has(key)) {
        const an = number(av);
        const bn = number(bv);

        // Missing numeric values always sort last.
        if (an === null && bn !== null) return 1;
        if (an !== null && bn === null) return -1;

        if (
          an !== null &&
          bn !== null &&
          an !== bn
        ) {
          return (an - bn) * (descending ? -1 : 1);
        }
      }

      return collator.compare(av, bv) *
        (descending ? -1 : 1);
    }

    headers.forEach(header => {
      const button = header.querySelector('button');

      if (!button) return;

      button.addEventListener('click', () => {
        const key = header.dataset.vialSort;

        descending =
          active === key ? !descending : false;

        active = key;

        // Only actual vial rows participate.
        // The empty-state row is left untouched.
        const rows = [...body.rows].filter(
          row => row.querySelector('.bulk-vial-check')
        );

        // Preserve original order for equal values.
        const order = new Map(
          rows.map((row, index) => [row, index])
        );

        rows.sort(
          (a, b) =>
            compareRows(a, b, key) ||
            order.get(a) - order.get(b)
        );

        const fragment =
          document.createDocumentFragment();

        rows.forEach(row => fragment.appendChild(row));

        body.appendChild(fragment);

        headers.forEach(h => {
          h.setAttribute(
            'aria-sort',
            h === header
              ? (descending ? 'descending' : 'ascending')
              : 'none'
          );
        });
      });
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
