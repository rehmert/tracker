/* Release 500: filter reusable foods in-place, without changing logged records. */
document.addEventListener('DOMContentLoaded', () => {
  'use strict';
  const root = document.getElementById('food-quick-log');
  const search = document.getElementById('food500-quick-search');
  const scope = document.getElementById('food500-quick-scope');
  const reset = document.getElementById('food500-quick-reset');
  const count = document.getElementById('food500-quick-count');
  const empty = document.getElementById('food500-quick-empty');
  const recent = document.getElementById('food500-recent');
  if (!root || !search || !scope || !reset || !count || !empty) return;

  const cards = [...root.querySelectorAll('[data-food500-quick-card]')];
  const normalize = text => String(text || '').normalize('NFKC')
    .toLocaleLowerCase().trim();
  // Index stable labels once, rather than normalize every card on every
  // mobile keystroke. Server-supplied products remain the only source.
  const entries = cards.map(card => ({
    card,
    searchable: normalize(
      card.dataset.food500Name + ' ' + card.dataset.food500Serving
    )
  }));
  let pending = false;

  function update() {
    const term = normalize(search.value);
    const section = scope.value;
    let matches = 0;
    let recentMatches = 0;
    for (const {card, searchable} of entries) {
      const isRecent = card.dataset.food500Scope === 'recent';
      const allowed = section === 'all' || card.dataset.food500Scope === section;
      const visible = allowed && (!term || searchable.includes(term));
      card.hidden = !visible;
      if (visible) {
        matches++;
        if (isRecent) recentMatches++;
      }
    }
    if (recent && recentMatches && (term || section === 'recent')) {
      recent.open = true;
    }
    count.textContent = matches + ' of ' + cards.length +
      ' reusable food entries match these filters.';
    empty.hidden = matches !== 0 || cards.length === 0;
    reset.disabled = !term && section === 'all';
  }

  function scheduleUpdate() {
    if (pending) return;
    pending = true;
    requestAnimationFrame(() => {
      pending = false;
      update();
    });
  }

  search.addEventListener('input', scheduleUpdate);
  scope.addEventListener('change', update);
  reset.addEventListener('click', () => {
    search.value = '';
    scope.value = 'all';
    update();
    search.focus();
  });
  update();
});
