/* Release 603: purchase-list phone cards and optional field disclosure.
 * Canonical purchase table rows, data, sort and filter are unchanged.
 * No fetch, form submission, or purchase writes.
 */
(() => {
  'use strict';
  const KEY = 'tracker.purchases.mobile-view603';
  const mq = window.matchMedia('(max-width: 760px)');

  function init() {
    // All native fields remain active when this disclosure is closed.
    // Desktop starts open via HTML and never loses access to extra fields.
    document.querySelectorAll('[data-mobile-optional603]').forEach(details => {
      if (mq.matches) details.open = false;
      if (mq.addEventListener) {
        mq.addEventListener('change', event => {
          if (!event.matches) details.open = true;
        });
      }
    });

    const more = document.querySelector('.purchase-review-more603');
    const active = more?.querySelector('[data-purchase-date-active603]');
    const from = more?.querySelector('[data-purchase-from]');
    const through = more?.querySelector('[data-purchase-through]');
    if (active && from && through) {
      const updateDateMarker = () => {
        active.hidden = !Boolean(from.value || through.value);
      };
      for (const field of [from, through]) {
        field.addEventListener('input', updateDateMarker);
        field.addEventListener('change', updateDateMarker);
      }
      // Reset is owned by the original purchase-review module. Run after
      // its synchronous input reset without interfering with its handlers.
      document.querySelector('[data-purchase-reset]')?.addEventListener(
        'click', () => requestAnimationFrame(updateDateMarker)
      );
      updateDateMarker();
    }

    const table = document.querySelector('[data-purchase-history]');
    if (!table || table.dataset.mobile603) return;
    const wrapper = table.closest('.scroll');
    if (!wrapper) return;
    table.dataset.mobile603 = '1';

    const labels = [
      'Date', 'Vendor', 'Order', 'Vials', 'Supplies / pills',
      'Total', 'Next step'
    ];
    table.querySelectorAll('tbody tr[data-purchase-row]').forEach(row => {
      if (row.cells.length !== labels.length) return;
      Array.from(row.cells).forEach((cell, i) => {
        cell.dataset.purchaseLabel603 = labels[i];
      });
    });

    const bar = document.createElement('div');
    bar.className = 'tracker-purchase-mobile-controls603';
    bar.setAttribute('aria-label', 'Mobile purchase presentation');
    const hint = document.createElement('span');
    const toggle = document.createElement('button');
    toggle.type = 'button';
    toggle.setAttribute('aria-controls', table.id);
    bar.append(hint, toggle);
    wrapper.before(bar);

    let mode = 'cards';
    try {
      if (localStorage.getItem(KEY) === 'table') mode = 'table';
    } catch (_) { /* Optional preference; never purchase data. */ }

    function render() {
      const cards = mq.matches && mode === 'cards';
      table.classList.toggle('tracker-purchase-cards603', cards);
      wrapper.classList.toggle('tracker-purchase-card-wrap603', cards);
      toggle.textContent = cards ? 'Full sortable table' : 'Card view';
      toggle.setAttribute('aria-pressed', String(cards));
      hint.textContent = cards
        ? 'Purchases · Cards' : 'Purchases · Full table';
    }
    toggle.addEventListener('click', () => {
      mode = mode === 'cards' ? 'table' : 'cards';
      try { localStorage.setItem(KEY, mode); }
      catch (_) { /* Optional. */ }
      render();
    });
    if (mq.addEventListener) mq.addEventListener('change', render);
    else mq.addListener(render);
    render();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init, {once:true});
  } else {
    init();
  }
})();
