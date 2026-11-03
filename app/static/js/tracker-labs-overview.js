/* Lab overview tools are display-only. No lab values or filters are stored. */
(() => {
  'use strict';

  const clean = value => String(value || '').normalize('NFKC').toLocaleLowerCase().trim();

  function initialize() {
    const grid = document.getElementById('labs-trend-grid');
    const search = document.getElementById('labs-analyte-search');
    const status = document.getElementById('labs-range-filter');
    const sort = document.getElementById('labs-trend-sort');
    const count = document.getElementById('labs-trend-count');
    const empty = document.getElementById('labs-trend-empty');
    const clear = document.getElementById('labs-trend-clear');

    if (grid && search && status && sort && count && empty && clear) {
      const cards = [...grid.querySelectorAll('[data-labs-trend-card]')];
      const initial = new Map(cards.map((card, index) => [card, index]));

      function compare(a, b) {
        const mode = sort.value;
        const dateCompare = b.dataset.labDate.localeCompare(a.dataset.labDate);
        const nameCompare = a.dataset.labName.localeCompare(
          b.dataset.labName, undefined, {sensitivity: 'base', numeric: true}
        );
        const countCompare = Number(b.dataset.labResults) - Number(a.dataset.labResults);
        let result = 0;
        if (mode === 'name-asc') result = nameCompare;
        else if (mode === 'name-desc') result = -nameCompare;
        else if (mode === 'results-desc') result = countCompare || dateCompare;
        else result = dateCompare;
        return result || initial.get(a) - initial.get(b);
      }

      function updateTrends() {
        const query = clean(search.value);
        const filter = status.value;
        const ordered = [...cards].sort(compare);
        let visible = 0;
        for (const card of ordered) {
          const state = card.dataset.labStatus;
          const matchesStatus = filter === 'all' || filter === state ||
            (filter === 'outside' && (state === 'above' || state === 'below'));
          const matchesName = !query || clean(card.dataset.labName).includes(query);
          const show = matchesStatus && matchesName;
          card.hidden = !show;
          if (show) visible++;
          grid.appendChild(card);
        }
        count.textContent = 'Showing ' + visible + ' of ' + cards.length + ' analytes.';
        empty.hidden = visible !== 0;
        clear.disabled = !query && filter === 'all' && sort.value === 'recent';
      }

      search.addEventListener('input', updateTrends);
      status.addEventListener('change', updateTrends);
      sort.addEventListener('change', updateTrends);
      clear.addEventListener('click', () => {
        search.value = '';
        status.value = 'all';
        sort.value = 'recent';
        updateTrends();
        search.focus();
      });
      updateTrends();
    }

    const reportTable = document.getElementById('labs-reports-table');
    const reportSearch = document.getElementById('labs-report-search');
    const reportCount = document.getElementById('labs-reports-count');
    const reportEmpty = document.getElementById('labs-reports-empty');
    const reportClear = document.getElementById('labs-reports-clear');

    if (reportTable && reportSearch && reportCount && reportEmpty && reportClear) {
      const rows = [...reportTable.querySelectorAll('tbody [data-labs-report-row]')];
      function updateReports() {
        const query = clean(reportSearch.value);
        let visible = 0;
        for (const row of rows) {
          const searchable = clean(row.dataset.labReportDate + ' ' +
            row.dataset.labReportName + ' ' +
            (row.cells[0]?.textContent || ''));
          const show = !query || searchable.includes(query);
          row.hidden = !show;
          if (show) visible++;
        }
        reportCount.textContent = 'Showing ' + visible + ' of ' + rows.length + ' reports.';
        reportEmpty.hidden = visible !== 0 || rows.length === 0;
        reportClear.disabled = !query;
      }
      reportSearch.addEventListener('input', updateReports);
      reportClear.addEventListener('click', () => {
        reportSearch.value = '';
        updateReports();
        reportSearch.focus();
      });
      updateReports();
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initialize, {once: true});
  } else {
    initialize();
  }
})();
