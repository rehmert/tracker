/* Release 602: mobile cards for existing Dose History rows.
 * Read-only DOM decoration; HTMX still owns the canonical tbody and deletes.
 */
(() => {
  'use strict';
  function initialize() {
    const body = document.getElementById('dose-body');
    if (!body || body.dataset.history602) return;
    body.dataset.history602 = '1';

    function decorate() {
      for (const row of body.rows) {
        if (row.cells.length !== 8 || row.dataset.doseHistory602) continue;
        row.dataset.doseHistory602 = '1';

        const action = row.cells[7];
        const details = document.createElement('button');
        details.type = 'button';
        details.className = 'tracker-dose-history-toggle602';
        details.textContent = 'More details';
        details.setAttribute('aria-expanded', 'false');
        action.appendChild(details);

        details.addEventListener('click', () => {
          const next = row.dataset.expanded602 !== 'true';
          row.dataset.expanded602 = String(next);
          details.setAttribute('aria-expanded', String(next));
          details.textContent = next ? 'Fewer details' : 'More details';
        });
      }
    }

    document.body.addEventListener('htmx:afterSwap', event => {
      if (event.target === body || body.contains(event.target)) {
        requestAnimationFrame(decorate);
      }
    });
    // The server can also replace row content in-place after a save.
    document.body.addEventListener('tracker:dose-saved', () => {
      requestAnimationFrame(decorate);
    });
    decorate();
  }
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initialize, {once:true});
  } else {
    initialize();
  }
})();
