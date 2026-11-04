/* Lab comparisons are display-only; the server owns values and unit conversion. */
(() => {
  'use strict';

  function initialize() {
    const root = document.getElementById('lab-compare-results');
    const table = document.getElementById('lab-compare-table');
    const search = document.getElementById('lab-compare-search');
    const filter = document.getElementById('lab-compare-filter');
    const sort = document.getElementById('lab-compare-sort');
    const reset = document.getElementById('lab-compare-reset');
    const exportButton = document.getElementById('lab-compare-export');
    const count = document.getElementById('lab-compare-count');
    const empty = document.getElementById('lab-compare-empty');

    if (!root || !table || !search || !filter || !sort ||
        !reset || !exportButton || !count || !empty) return;

    const body = table.tBodies[0];
    if (!body) return;
    const rows = [...body.querySelectorAll('[data-lab-compare-row]')];
    const original = new Map(rows.map((row, i) => [row, i]));
    const priority = {
      incompatible: 0, 'only-a': 1, 'only-b': 2, different: 3, same: 4
    };
    const labels = {
      incompatible: 'Units not convertible',
      'only-a': 'Only Report A',
      'only-b': 'Only Report B',
      different: 'Nonzero difference',
      same: 'Zero difference'
    };

    function visibleRows() {
      // Export in the same current DOM order shown to the
      // user, including active sort and filter settings.
      return [...body.querySelectorAll(
        '[data-lab-compare-row]'
      )].filter(row => !row.hidden);
    }

    function matches(row, query, mode) {
      const state = row.dataset.state;
      if (!row.dataset.analyte.toLocaleLowerCase().includes(query)) return false;
      if (mode === 'all') return true;
      if (mode === 'comparable') return state === 'same' || state === 'different';
      if (mode === 'needs-review') {
        return state === 'incompatible' || state === 'only-a' || state === 'only-b';
      }
      return state === mode;
    }

    function order(a, b) {
      const nameOrder = a.dataset.analyte.localeCompare(b.dataset.analyte,
        undefined, {sensitivity: 'base', numeric: true});
      let result = nameOrder;
      if (sort.value === 'name-desc') result = -nameOrder;
      if (sort.value === 'review-first') {
        result = (priority[a.dataset.state] ?? 99) -
          (priority[b.dataset.state] ?? 99) || nameOrder;
      }
      return result || original.get(a) - original.get(b);
    }

    function update() {
      const query = search.value.trim().toLocaleLowerCase();
      const mode = filter.value;
      let shown = 0;
      for (const row of [...rows].sort(order)) {
        row.hidden = !matches(row, query, mode);
        if (!row.hidden) shown++;
        body.appendChild(row);
      }
      count.textContent = 'Showing ' + shown + ' of ' + rows.length + ' analytes.';
      empty.hidden = shown !== 0;
      exportButton.disabled = shown === 0;
      reset.disabled = !query && mode === 'all' && sort.value === 'name-asc';
    }

    function csvCell(value, numeric = false) {
      const originalValue = String(value ?? '');
      const isNumber = numeric && /^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:e[+-]?\d+)?$/i.test(originalValue);
      const formulaLike = /^[\s\u0000-\u001f]*[=+\-@]/.test(originalValue) ||
        /^[\t\r\n]/.test(originalValue);
      const safe = !isNumber && formulaLike ? "'" + originalValue : originalValue;
      return '"' + safe.replaceAll('"', '""') + '"';
    }

    function exportFilteredCsv() {
      const current = visibleRows();
      if (!current.length) return;
      const header = [
        'Report A date', 'Report B date', 'Analyte',
        'Report A value', 'Report A unit', 'Report B value', 'Report B unit',
        'Report B in A units', 'Difference A minus B', 'Comparison'
      ];
      const records = current.map(row => [
        root.dataset.reportADate, root.dataset.reportBDate,
        row.dataset.analyte, row.dataset.aValue, row.dataset.aUnit,
        row.dataset.bValue, row.dataset.bUnit,
        row.dataset.bConverted, row.dataset.delta,
        labels[row.dataset.state] || row.dataset.state
      ]);
      const csv = '\uFEFF' + [header, ...records].map((record, index) =>
        record.map((value, col) =>
          csvCell(value, index > 0 && [3, 5, 7, 8].includes(col))
        ).join(',')
      ).join('\r\n') + '\r\n';
      const blob = new Blob([csv], {type:'text/csv;charset=utf-8'});
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement('a');
      anchor.href = url;
      anchor.download = 'tracker-lab-report-comparison.csv';
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    }

    search.addEventListener('input', update);
    filter.addEventListener('change', update);
    sort.addEventListener('change', update);
    reset.addEventListener('click', () => {
      search.value = '';
      filter.value = 'all';
      sort.value = 'name-asc';
      update();
      search.focus();
    });
    exportButton.addEventListener('click', exportFilteredCsv);
    update();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initialize, {once:true});
  } else {
    initialize();
  }
})();
