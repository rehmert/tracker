(() => {
  'use strict';

  const STORAGE_KEY = 'tracker.vitals.table.v1';

  function initialize() {
    const table = document.querySelector(
      '[data-vitals-table]'
    );

    if (!table) return;

    const tbody = table.tBodies[0];

    if (!tbody) return;

    const rows = Array.from(
      tbody.querySelectorAll('tr')
    ).filter(row => row.querySelectorAll('td').length >= 7);

    if (!rows.length) return;

    const toolbar = document.querySelector(
      '[data-vitals-toolbar]'
    );

    if (!toolbar) return;

    const search = toolbar.querySelector(
      '[data-vitals-search]'
    );

    const type = toolbar.querySelector(
      '[data-vitals-type]'
    );

    const sort = toolbar.querySelector(
      '[data-vitals-sort]'
    );

    const count = toolbar.querySelector(
      '[data-vitals-count]'
    );

    const exportButton = toolbar.querySelector(
      '[data-vitals-export]'
    );

    const resetButton = toolbar.querySelector(
      '[data-vitals-reset]'
    );

    const state = {
      search: '',
      type: 'all',
      sort: 'date-desc'
    };

    try {
      const saved = JSON.parse(
        localStorage.getItem(STORAGE_KEY) || '{}'
      );

      if (typeof saved.search === 'string') {
        state.search = saved.search;
      }

      if (typeof saved.type === 'string') {
        state.type = saved.type;
      }

      if (typeof saved.sort === 'string') {
        state.sort = saved.sort;
      }
    } catch (_) {
      // Storage may be disabled.
    }

    const allowedTypes = new Set([
      'all',
      'weight',
      'bp',
      'pulse'
    ]);

    const allowedSorts = new Set([
      'date-desc',
      'date-asc',
      'weight-desc',
      'weight-asc',
      'sys-desc',
      'sys-asc',
      'dia-desc',
      'dia-asc',
      'pulse-desc',
      'pulse-asc'
    ]);

    if (!allowedTypes.has(state.type)) {
      state.type = 'all';
    }

    if (!allowedSorts.has(state.sort)) {
      state.sort = 'date-desc';
    }

    search.value = state.search;
    type.value = state.type;
    sort.value = state.sort;

    const original = new Map(
      rows.map((row, index) => [row, index])
    );

    function cellText(row, index) {
      return (
        row.cells[index]?.textContent || ''
      ).trim();
    }

    function number(text) {
      const normalized = String(text)
        .replace(/,/g, '')
        .trim();

      if (
        !normalized ||
        normalized === '—' ||
        normalized === '-'
      ) {
        return null;
      }

      const value = Number(normalized);

      return Number.isFinite(value) ? value : null;
    }

    function bp(row) {
      const text = cellText(row, 2);

      const match = text.match(
        /(\d+)\s*\/\s*(\d+)/
      );

      return match
        ? [Number(match[1]), Number(match[2])]
        : [null, null];
    }

    function measurement(row, key) {
      if (key === 'weight') {
        return number(cellText(row, 1));
      }

      if (key === 'pulse') {
        return number(cellText(row, 3));
      }

      const pressure = bp(row);

      if (key === 'sys') return pressure[0];
      if (key === 'dia') return pressure[1];

      return null;
    }

    function matchesType(row) {
      switch (state.type) {
        case 'weight':
          return measurement(row, 'weight') !== null;

        case 'bp':
          return measurement(row, 'sys') !== null;

        case 'pulse':
          return measurement(row, 'pulse') !== null;

        default:
          return true;
      }
    }

    function matchesSearch(row) {
      const query = state.search
        .trim()
        .toLocaleLowerCase();

      if (!query) return true;

      return Array.from(row.cells)
        .slice(0, 6)
        .some(cell =>
          cell.textContent
            .toLocaleLowerCase()
            .includes(query)
        );
    }

    function compareRows(a, b) {
      const [key, direction] = state.sort.split('-');

      const multiplier = direction === 'asc' ? 1 : -1;

      if (key === 'date') {
        // Dates are rendered by Tracker's display filter.
        // Preserve database ordering for chronological sorting.
        return multiplier * (
          original.get(a) - original.get(b)
        ) * -1;
      }

      const av = measurement(a, key);
      const bv = measurement(b, key);

      if (av === null && bv === null) {
        return original.get(a) - original.get(b);
      }

      if (av === null) return 1;
      if (bv === null) return -1;

      const difference = (av - bv) * multiplier;

      return difference || (
        original.get(a) - original.get(b)
      );
    }

    function saveState() {
      try {
        localStorage.setItem(
          STORAGE_KEY,
          JSON.stringify(state)
        );
      } catch (_) {
        // Preferences are optional.
      }
    }

    function visibleRows() {
      return rows.filter(
        row => !row.hidden
      );
    }

    function update() {
      const sorted = [...rows].sort(compareRows);

      for (const row of sorted) {
        row.hidden = !(
          matchesType(row) &&
          matchesSearch(row)
        );

        tbody.appendChild(row);
      }

      const visible = visibleRows().length;

      count.textContent =
        `${visible} of ${rows.length} readings`;

      exportButton.disabled = visible === 0;

      saveState();
    }

    function csvEscape(value) {
      const text = String(value ?? '');

      // Prefix formula-like values to prevent spreadsheet
      // software from interpreting exported text as formulas.
      const safe = /^[\s]*[=+\-@\t\r]/.test(text)
        ? "'" + text
        : text;

      return '"' + safe.replace(/"/g, '""') + '"';
    }

    function exportCsv() {
      const header = [
        'When',
        'Weight',
        'Blood pressure',
        'Pulse',
        'Context',
        'Notes'
      ];

      const data = visibleRows().map(row =>
        Array.from(row.cells)
          .slice(0, 6)
          .map(cell => cell.textContent.trim())
      );

      const csv = [header, ...data]
        .map(values => values.map(csvEscape).join(','))
        .join('\r\n');

      const blob = new Blob(
        ['\uFEFF', csv, '\r\n'],
        { type: 'text/csv;charset=utf-8' }
      );

      const url = URL.createObjectURL(blob);

      const anchor = document.createElement('a');

      anchor.href = url;
      anchor.download =
        'tracker-vitals-' +
        new Date().toISOString().slice(0, 10) +
        '.csv';

      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();

      setTimeout(() => {
        URL.revokeObjectURL(url);
      }, 1000);
    }

    search.addEventListener('input', () => {
      state.search = search.value;
      update();
    });

    type.addEventListener('change', () => {
      state.type = type.value;
      update();
    });

    sort.addEventListener('change', () => {
      state.sort = sort.value;
      update();
    });

    exportButton.addEventListener(
      'click',
      exportCsv
    );

    resetButton.addEventListener('click', () => {
      state.search = '';
      state.type = 'all';
      state.sort = 'date-desc';

      search.value = '';
      type.value = 'all';
      sort.value = 'date-desc';

      update();
      search.focus();
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
