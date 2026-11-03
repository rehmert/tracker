/* Calendar filtering is read-only. All event actions remain server-owned. */
(() => {
  'use strict';
  function init() {
    const root = document.getElementById('calendar-workbench');
    const grid = document.getElementById('calendar-grid');
    if (!root || !grid) return;
    const search = document.getElementById('calendar-search');
    const choice = document.getElementById('calendar-status-filter');
    const reset = document.getElementById('calendar-reset-filters');
    const print = document.getElementById('calendar-print');
    const summary = document.getElementById('calendar-filter-summary');
    if (!search || !choice || !reset || !print || !summary) return;

    const events = [...grid.querySelectorAll('.calendar-activity')];
    const days = [...grid.querySelectorAll('.calendar-day')];
    const normalize = value => String(value || '').normalize('NFKC')
      .toLocaleLowerCase().trim();

    function update() {
      const query = normalize(search.value);
      const filter = choice.value;
      let visible = 0;
      for (const item of events) {
        const status = item.dataset.calendarStatus;
        const matchesStatus = filter === 'all' || status === filter ||
          (filter === 'needs-action' && (status === 'due' || status === 'unrecorded'));
        const matchesText = !query || normalize(item.dataset.calendarSearch).includes(query);
        const show = matchesStatus && matchesText;
        item.hidden = !show;
        if (show) visible += 1;
      }
      for (const day of days) {
        const items = [...day.querySelectorAll('.calendar-activity')];
        day.classList.toggle('calendar-filtered-empty',
          items.length > 0 && items.every(item => item.hidden));
      }
      summary.textContent = 'Showing ' + visible + ' of ' +
        events.length + ' entries in this month.';
      if (!visible && events.length) {
        summary.textContent += ' No matches; clear filters to show all entries.';
      }
      reset.disabled = !query && filter === 'all';
    }

    search.addEventListener('input', update);
    choice.addEventListener('change', update);
    reset.addEventListener('click', () => {
      search.value = '';
      choice.value = 'all';
      update();
      search.focus();
    });
    print.addEventListener('click', () => {
      if (typeof window.print === 'function') window.print();
    });
    update();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init, {once:true});
  } else {
    init();
  }
})();
