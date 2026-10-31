/*
 * Tracker Stage 34.3
 * Interactive inventory attention navigation.
 *
 * Uses badges created by Stage 34.2.
 * Does not change inventory, forms, or row visibility.
 */
(() => {
  'use strict';

  const CATEGORIES = [
    ['expired', 'Past date'],
    ['soon', 'Approaching date'],
    ['low', 'Low inventory'],
    ['depleted', 'Depleted']
  ];

  function initialize() {
    const panel = document.getElementById(
      'tracker-vial-attention'
    );
    const table = document.getElementById(
      'tracker-vials-sortable'
    );

    if (!panel || !table) return;

    const rows = Array.from(
      table.querySelectorAll(
        'tbody tr[data-attention-status]'
      )
    );

    const matchesByCategory = new Map();

    function categoriesFor(row) {
      const badges = Array.from(
        row.querySelectorAll(
          '.tracker-attention-badge'
        )
      );

      const labels = badges.map(
        badge => badge.textContent.toLowerCase()
      );

      const past = labels.some(
        label => label.includes('date passed')
      );

      const approaching = !past && labels.some(
        label =>
          label.startsWith('expiration:') ||
          label.startsWith('beyond-use:')
      );

      return {
        expired: past,
        soon: approaching,
        low: labels.includes('low inventory'),
        depleted: labels.includes('depleted')
      };
    }

    for (const [key] of CATEGORIES) {
      matchesByCategory.set(
        key,
        rows.filter(row => categoriesFor(row)[key])
      );
    }

    const style = document.createElement('style');
    style.textContent = `
      #tracker-vial-attention
      .tracker-attention-action {
        cursor:pointer;
        border:1px solid var(--border,#bbb);
        border-radius:.45rem;
        padding:.4rem .65rem;
        background:transparent;
        color:inherit;
        font:inherit;
      }

      #tracker-vial-attention
      .tracker-attention-action[aria-pressed="true"] {
        border-color:var(--accent,#2563eb);
        box-shadow:0 0 0 2px
          var(--accent,#2563eb);
      }

      #tracker-vial-attention
      .tracker-attention-action:disabled {
        opacity:.5;
        cursor:default;
      }

      #tracker-attention-navigation {
        display:flex;
        flex-wrap:wrap;
        align-items:center;
        gap:.5rem;
        margin-top:.75rem;
      }

      #tracker-attention-navigation[hidden] {
        display:none;
      }

      #tracker-vials-sortable
      tr.tracker-attention-match > td {
        box-shadow:inset 0 0 0 9999px
          rgba(245,158,11,.08);
      }

      #tracker-vials-sortable
      tr.tracker-attention-current {
        outline:2px solid var(--accent,#2563eb);
        outline-offset:-2px;
      }

      #tracker-vials-sortable
      tr.tracker-attention-current > td {
        box-shadow:inset 0 0 0 9999px
          rgba(59,130,246,.16);
      }
    `;
    document.head.appendChild(style);

    const controls = new Map();

    let active = null;
    let current = -1;

    const navigation = document.createElement('div');
    navigation.id = 'tracker-attention-navigation';
    navigation.hidden = true;

    const summary = document.createElement('span');
    summary.id = 'tracker-attention-position';
    summary.setAttribute('role', 'status');
    summary.setAttribute('aria-live', 'polite');

    function button(label, handler) {
      const element = document.createElement('button');
      element.type = 'button';
      element.textContent = label;
      element.addEventListener('click', handler);
      return element;
    }

    const previous = button('Previous', () => move(-1));
    const next = button('Next', () => move(1));
    const clear = button('Clear attention', clearAttention);

    navigation.append(
      summary,
      previous,
      next,
      clear
    );

    panel.appendChild(navigation);

    function clearHighlights() {
      rows.forEach(row => {
        row.classList.remove(
          'tracker-attention-match',
          'tracker-attention-current'
        );
      });
    }

    function clearAttention() {
      active = null;
      current = -1;
      clearHighlights();

      controls.forEach(control => {
        control.setAttribute('aria-pressed', 'false');
      });

      navigation.hidden = true;
    }

    function orderedMatches() {
      if (!active) return [];

      const members = new Set(
        matchesByCategory.get(active) || []
      );

      // Read current DOM order so navigation respects
      // subsequent column sorting.
      return Array.from(
        table.querySelectorAll(
          'tbody tr[data-attention-status]'
        )
      ).filter(row => members.has(row));
    }

    function move(direction) {
      const matches = orderedMatches();
      if (!matches.length) return;

      if (current >= 0) {
        const old = table.querySelector(
          'tr.tracker-attention-current'
        );
        if (old) {
          old.classList.remove(
            'tracker-attention-current'
          );
        }
      }

      current = (
        current + direction + matches.length
      ) % matches.length;

      const row = matches[current];

      row.classList.add(
        'tracker-attention-current'
      );

      summary.textContent =
        `${activeLabel(active)}: ` +
        `${current + 1} of ${matches.length}`;

      row.scrollIntoView({
        behavior:'auto',
        block:'center'
      });
    }

    function activeLabel(key) {
      const item = CATEGORIES.find(
        category => category[0] === key
      );
      return item ? item[1] : key;
    }

    function activate(key) {
      if (active === key) {
        clearAttention();
        return;
      }

      clearAttention();

      active = key;
      current = -1;

      const matches = orderedMatches();

      if (!matches.length) {
        clearAttention();
        return;
      }

      matches.forEach(row => {
        row.classList.add(
          'tracker-attention-match'
        );
      });

      controls.get(key).setAttribute(
        'aria-pressed',
        'true'
      );

      navigation.hidden = false;
      move(1);
    }

    CATEGORIES.forEach(([key, label]) => {
      const original = document.getElementById(
        'tracker-attention-' + key
      );

      if (!original) return;

      const action = document.createElement('button');
      action.type = 'button';
      action.id = original.id;
      action.className =
        'tracker-attention-action';
      action.textContent = original.textContent;
      action.setAttribute('aria-label', label);
      action.setAttribute('aria-pressed', 'false');

      const count = matchesByCategory.get(key).length;

      action.disabled = count === 0;

      action.addEventListener(
        'click',
        () => activate(key)
      );

      original.replaceWith(action);
      controls.set(key, action);
    });

    // Keyboard shortcut while focus is inside
    // the attention navigation controls.
    navigation.addEventListener(
      'keydown',
      event => {
        if (event.key === 'ArrowRight') {
          event.preventDefault();
          move(1);
        } else if (event.key === 'ArrowLeft') {
          event.preventDefault();
          move(-1);
        } else if (event.key === 'Escape') {
          clearAttention();
        }
      }
    );
  }

  if (document.readyState === 'loading') {
    document.addEventListener(
      'DOMContentLoaded',
      initialize,
      { once:true }
    );
  } else {
    initialize();
  }
})();
