/* Tracker Workflow Release: local-only vial search; never changes inventory. */
(() => {
  'use strict';
  function init() {
    const input = document.getElementById('tracker-vial-search');
    const table = document.getElementById('tracker-available-vials');
    if (!input || !table) return;
    const rows = Array.from(table.querySelectorAll('[data-tracker-vial-row]'));
    const count = document.getElementById('tracker-vial-count');
    const empty = document.getElementById('tracker-vial-no-matches');
    const clear = document.getElementById('tracker-vial-clear');
    const reset = document.getElementById('tracker-vial-reset');
    function update() {
      const query = input.value.trim().toLocaleLowerCase();
      let visible = 0;
      rows.forEach(row => {
        const match = !query || row.textContent.toLocaleLowerCase().includes(query);
        row.hidden = !match;
        if (match) visible++;
      });
      if (count) count.textContent = `${visible} of ${rows.length} vials shown`;
      if (empty) empty.hidden = visible !== 0;
      if (clear) clear.hidden = !query;
    }
    function resetSearch() { input.value = ''; update(); input.focus(); }
    input.addEventListener('input', update);
    if (clear) clear.addEventListener('click', resetSearch);
    if (reset) reset.addEventListener('click', resetSearch);
    update();
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();
})();
