/* Release 601: project the existing vial table as optional phone cards.
 * The same cells, links, checkboxes, row order, pagination, and form handlers
 * remain authoritative. Only their presentation changes.
 */
(() => {
  'use strict';
  const KEY = 'tracker.vials.mobile-view601';
  const mobile = window.matchMedia('(max-width: 760px)');
  const labels = [
    'Select', 'Compound', 'Vial', 'Remaining', 'Amount left',
    'Landed cost', 'Unit cost', 'COA', 'Status', 'Vendor'
  ];

  function init() {
    const table = document.getElementById('tracker-vials-sortable');
    if (!table || table.dataset.mobileCards601) return;
    table.dataset.mobileCards601 = '1';

    const wrapper = table.closest('.scroll');
    if (!wrapper) return;

    const bar = document.createElement('div');
    bar.className = 'tracker-vial-mobile-controls601';
    bar.setAttribute('aria-label', 'Mobile vial presentation');

    const hint = document.createElement('span');
    const toggle = document.createElement('button');
    toggle.type = 'button';
    toggle.setAttribute('aria-controls', table.id);
    bar.append(hint, toggle);
    wrapper.before(bar);

    // Add labels to the existing cells. Do not clone rows: bulk selection,
    // paging, sorting and saved views depend on these very same DOM nodes.
    table.querySelectorAll('tbody > tr').forEach(row => {
      const cells = Array.from(row.cells);
      if (cells.length !== labels.length) return; // empty-state row
      cells.forEach((cell, index) => {
        cell.dataset.label = labels[index];
      });
      const id = row.querySelector('input.bulk-vial-check')?.value;
      if (!id) return;
      const button = document.createElement('button');
      button.type = 'button';
      button.className = 'tracker-vial-detail-toggle601';
      button.setAttribute('aria-expanded', 'false');
      button.setAttribute('aria-label', 'Show details for vial #' + id);
      // CSS renders the label; textContent stays untouched for sorting/search.
      button.dataset.text = 'More details';
      cells[2].append(button);
      button.addEventListener('click', () => {
        const expanded = row.dataset.vialExpanded601 !== 'true';
        row.dataset.vialExpanded601 = String(expanded);
        button.setAttribute('aria-expanded', String(expanded));
        button.setAttribute('aria-label',
          (expanded ? 'Hide' : 'Show') + ' details for vial #' + id);
        button.dataset.text = expanded ? 'Less details' : 'More details';
      });
    });

    let mode = 'cards';
    try {
      if (localStorage.getItem(KEY) === 'table') mode = 'table';
    } catch (_) { /* local storage is optional */ }

    function render() {
      const cardView = mobile.matches && mode === 'cards';
      table.classList.toggle('tracker-vials-as-cards601', cardView);
      toggle.textContent = cardView ? 'Full table' : 'Card view';
      toggle.setAttribute('aria-pressed', String(cardView));
      hint.textContent = cardView
        ? 'Vials · Compact cards'
        : 'Vials · Full table';
    }

    toggle.addEventListener('click', () => {
      mode = mode === 'cards' ? 'table' : 'cards';
      try { localStorage.setItem(KEY, mode); } catch (_) { /* optional */ }
      render();
    });

    if (mobile.addEventListener) {
      mobile.addEventListener('change', render);
    } else {
      mobile.addListener(render);
    }
    render();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init, {once:true});
  } else {
    init();
  }
})();
