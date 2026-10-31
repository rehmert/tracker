/*
 * Tracker Stage 34.6
 * Recent Administration Search and Navigation
 *
 * Read-only UI enhancement.
 * Does not modify dose records or inventory.
 */

(() => {
  'use strict';

  function initialize() {
    const section = document.getElementById(
      'tracker-history-section'
    );

    const table = document.getElementById(
      'tracker-history-table'
    );

    const input = document.getElementById(
      'tracker-history-search'
    );

    const clear = document.getElementById(
      'tracker-history-clear'
    );

    const count = document.getElementById(
      'tracker-history-count'
    );

    const previous = document.getElementById(
      'tracker-history-previous'
    );

    const next = document.getElementById(
      'tracker-history-next'
    );

    const position = document.getElementById(
      'tracker-history-position'
    );

    const empty = document.getElementById(
      'tracker-history-empty'
    );

    if (
      !section ||
      !table ||
      !input ||
      !clear ||
      !count ||
      !previous ||
      !next ||
      !position ||
      !empty
    ) {
      return;
    }

    const rows = Array.from(
      table.querySelectorAll('tbody tr')
    );

    let matches = [];
    let current = -1;

    const style = document.createElement('style');

    style.textContent = `
      #tracker-history-controls {
        display:flex;
        flex-wrap:wrap;
        align-items:center;
        gap:.65rem;
        margin:.75rem 0;
      }

      #tracker-history-controls input {
        flex:1 1 240px;
        min-width:150px;
      }

      #tracker-history-navigation {
        display:flex;
        align-items:center;
        flex-wrap:wrap;
        gap:.5rem;
        margin:.5rem 0;
      }

      #tracker-history-navigation button:disabled {
        opacity:.45;
        cursor:default;
      }

      #tracker-history-table
      tr.tracker-history-current {
        outline:2px solid var(--accent,#2563eb);
        outline-offset:-2px;
      }

      #tracker-history-table
      tr.tracker-history-current > td {
        box-shadow:inset 0 0 0 9999px
          rgba(59,130,246,.12);
      }

      #tracker-history-empty[hidden] {
        display:none;
      }
    `;

    document.head.appendChild(style);

    function clearHighlight() {
      rows.forEach(row => {
        row.classList.remove(
          'tracker-history-current'
        );
      });
    }

    function updatePosition() {
      position.textContent =
        current < 0
          ? ''
          : `${current + 1} of ${matches.length}`;
    }

    function navigate(direction) {
      if (!matches.length) return;

      clearHighlight();

      current = (
        current + direction + matches.length
      ) % matches.length;

      const row = matches[current];

      row.classList.add(
        'tracker-history-current'
      );

      updatePosition();

      row.scrollIntoView({
        behavior:'auto',
        block:'center',
        inline:'nearest'
      });
    }

    function update() {
      const query = input.value
        .trim()
        .toLocaleLowerCase();

      clearHighlight();

      matches = rows.filter(row => {
        const text = row.textContent
          .toLocaleLowerCase();

        const match =
          !query || text.includes(query);

        row.hidden = !match;

        return match;
      });

      current = -1;

      count.textContent =
        `${matches.length} of ${rows.length} administrations shown`;

      clear.hidden = !query;

      empty.hidden = matches.length !== 0;

      previous.disabled = matches.length === 0;
      next.disabled = matches.length === 0;

      updatePosition();
    }

    function reset() {
      input.value = '';
      update();
      input.focus();
    }

    input.addEventListener('input', update);

    clear.addEventListener('click', reset);

    previous.addEventListener(
      'click',
      () => navigate(-1)
    );

    next.addEventListener(
      'click',
      () => navigate(1)
    );

    input.addEventListener('keydown', event => {
      if (event.key === 'Enter') {
        event.preventDefault();
        navigate(1);
      }

      if (event.key === 'Escape') {
        reset();
      }
    });

    update();
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
