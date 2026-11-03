/* Read-only supply consumption review. Server-provided usage and coverage are authoritative. */
(() => {
  'use strict';

  function initialize() {
    const table = document.getElementById('supply-consumption-table');
    const search = document.getElementById('supply-consumption-search');
    const kind = document.getElementById('supply-consumption-kind');
    const filter = document.getElementById('supply-consumption-filter');
    const sort = document.getElementById('supply-consumption-sort');
    const reset = document.getElementById('supply-consumption-reset');
    const exportButton = document.getElementById('supply-consumption-export');
    const count = document.getElementById('supply-consumption-count');
    const empty = document.getElementById('supply-consumption-empty');
    const total = document.getElementById('supply-consumption-total');
    const usedCount = document.getElementById('supply-consumption-used');
    const zeroCount = document.getElementById('supply-consumption-zero');
    const shortCount = document.getElementById('supply-consumption-short');

    if (!table || !table.tBodies[0] || table.dataset.consumptionReady ||
        ![search, kind, filter, sort, reset, exportButton, count, empty, total,
          usedCount, zeroCount, shortCount].every(Boolean)) return;

    const tbody = table.tBodies[0];
    const rows = [...tbody.querySelectorAll('[data-supply-consumption-row]')];
    const initialIndex = new Map(rows.map((row, index) => [row, index]));
    const collator = new Intl.Collator(undefined, {sensitivity:'base', numeric:true});

    function number(value) {
      if (String(value).trim() === '') return null;
      const parsed = Number(value);
      return Number.isFinite(parsed) ? parsed : null;
    }

    const records = rows.map(row => ({
      row,
      name: row.dataset.supplyName,
      kind: row.dataset.supplyKind,
      used: number(row.dataset.supplyUsed),
      remaining: number(row.dataset.supplyRemaining),
      rate: number(row.dataset.supplyRate),
      coverage: number(row.dataset.supplyCoverage)
    }));

    const kinds = new Map();
    for (const record of records) {
      if (!kinds.has(record.kind)) {
        kinds.set(record.kind, record.row.cells[1]?.textContent?.trim() || record.kind);
      }
    }
    for (const [value, label] of [...kinds]
      .sort((a, b) => collator.compare(a[1], b[1]))) {
      const option = document.createElement('option');
      option.value = value;
      option.textContent = label;
      kind.appendChild(option);
    }

    function isMatch(record, query, state) {
      const hasUsage = (record.used ?? 0) > 0;
      const coverage = record.coverage;
      const statusMatches =
        state === 'all' ||
        (state === 'no-usage' && !hasUsage) ||
        (state === 'zero-stock' && record.remaining !== null && record.remaining <= 0) ||
        (state === 'short-7' && coverage !== null && coverage <= 7) ||
        (state === 'short-30' && coverage !== null && coverage <= 30) ||
        (state === 'long-30' && coverage !== null && coverage > 30);
      return statusMatches &&
        (!query || record.name.toLocaleLowerCase().includes(query)) &&
        (!kind.value || kind.value === record.kind);
    }

    function compare(a, b) {
      const mode = sort.value;
      let cmp = 0;
      if (mode === 'name-asc' || mode === 'name-desc') {
        cmp = collator.compare(a.name, b.name) * (mode === 'name-desc' ? -1 : 1);
      } else {
        const field = mode === 'used-desc' ? 'used' :
          mode === 'remaining-asc' ? 'remaining' : 'coverage';
        const left = a[field];
        const right = b[field];
        // Supplies without an observed rate always sort after comparable coverage values.
        if (left === null && right !== null) return 1;
        if (right === null && left !== null) return -1;
        const direction = mode === 'used-desc' || mode === 'coverage-desc' ? -1 : 1;
        cmp = ((left ?? 0) - (right ?? 0)) * direction;
      }
      return cmp || initialIndex.get(a.row) - initialIndex.get(b.row);
    }

    function visible() {
      return records.filter(record => !record.row.hidden);
    }

    function update() {
      const query = search.value.trim().toLocaleLowerCase();
      let shown = 0, active = 0, zero = 0, short = 0;
      for (const record of [...records].sort(compare)) {
        const show = isMatch(record, query, filter.value);
        record.row.hidden = !show;
        record.row.style.display = show ? '' : 'none';
        tbody.appendChild(record.row);
        if (!show) continue;
        shown++;
        if ((record.used ?? 0) > 0) active++;
        if (record.remaining !== null && record.remaining <= 0) zero++;
        if (record.coverage !== null && record.coverage <= 30) short++;
      }
      total.textContent = String(shown);
      usedCount.textContent = String(active);
      zeroCount.textContent = String(zero);
      shortCount.textContent = String(short);
      count.textContent = 'Showing ' + shown + ' of ' + records.length + ' supplies.';
      empty.hidden = shown !== 0 || records.length === 0;
      exportButton.disabled = shown === 0;
      reset.disabled = !query && !kind.value &&
        filter.value === 'all' && sort.value === 'name-asc';
    }

    function csvCell(value, numeric = false) {
      const text = String(value ?? '');
      const literalNumber = numeric &&
        /^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:e[+-]?\d+)?$/i.test(text);
      const suspicious = /^[\s\u0000-\u001f]*[=+\-@]/.test(text) ||
        /^[\t\r\n]/.test(text);
      const safe = suspicious && !literalNumber ? "'" + text : text;
      return '"' + safe.replaceAll('"', '""') + '"';
    }

    function exportCsv() {
      const list = visible();
      if (!list.length) return;
      const headers = ['Period days', 'Supply', 'Type', 'Used in period',
        'Remaining', 'Average per day', 'Observed coverage days', 'Coverage note'];
      const data = list.map(record => [
        table.dataset.periodDays,
        record.name,
        record.row.cells[1]?.textContent?.trim() || record.kind,
        record.row.dataset.supplyUsed,
        record.row.dataset.supplyRemaining,
        record.row.dataset.supplyRate,
        record.row.dataset.supplyCoverage,
        record.coverage === null ? 'No recorded usage in period' : 'Historical rate estimate'
      ]);
      const csv = '\uFEFF' + [headers, ...data].map((line, rowIndex) =>
        line.map((value, index) =>
          csvCell(value, rowIndex > 0 && [0, 3, 4, 5, 6].includes(index))
        ).join(',')
      ).join('\r\n') + '\r\n';
      const blob = new Blob([csv], {type:'text/csv;charset=utf-8'});
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = 'tracker-supply-consumption-filtered.csv';
      document.body.appendChild(link);
      link.click();
      link.remove();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    }

    search.addEventListener('input', update);
    kind.addEventListener('change', update);
    filter.addEventListener('change', update);
    sort.addEventListener('change', update);
    reset.addEventListener('click', () => {
      search.value = '';
      kind.value = '';
      filter.value = 'all';
      sort.value = 'name-asc';
      update();
      search.focus();
    });
    exportButton.addEventListener('click', exportCsv);
    table.dataset.consumptionReady = '1';
    update();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initialize, {once:true});
  } else {
    initialize();
  }
})();
