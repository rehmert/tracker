/*
 * Tracker Stage 34.10
 * Administration History Insights
 *
 * Read-only frontend enhancement.
 * Uses existing history table and search.
 */

(() => {
  'use strict';

  function initialize() {
    const section = document.getElementById(
      'tracker-history-section'
    );

    const controls = document.getElementById(
      'tracker-history-controls'
    );

    const table = document.getElementById(
      'tracker-history-table'
    );

    const search = document.getElementById(
      'tracker-history-search'
    );

    if (!section || !controls || !table || !search) {
      return;
    }

    if (document.getElementById(
      'tracker-history-insights'
    )) {
      return;
    }

    const rows = Array.from(
      table.querySelectorAll('tbody tr')
    ).filter(row => row.cells.length >= 4);

    if (!rows.length) return;

    const style = document.createElement('style');

    style.textContent = `
      #tracker-history-insights {
        margin:.85rem 0 1rem;
        padding:1rem;
        border:1px solid var(--border,#ddd);
        border-radius:.75rem;
      }

      #tracker-history-insights h3 {
        margin:0 0 .35rem;
        font-size:1rem;
      }

      #tracker-history-insights .description {
        font-size:.85rem;
        opacity:.75;
        margin-bottom:.75rem;
      }

      #tracker-history-compounds {
        display:flex;
        flex-wrap:wrap;
        gap:.5rem;
      }

      #tracker-history-compounds button {
        display:inline-flex;
        align-items:center;
        gap:.5rem;
        padding:.4rem .7rem;
        border:1px solid var(--border,#ccc);
        border-radius:999px;
        background:transparent;
        color:inherit;
        cursor:pointer;
        font:inherit;
      }

      #tracker-history-compounds button:hover {
        border-color:var(--accent,#2563eb);
      }

      #tracker-history-compounds button:focus-visible {
        outline:2px solid var(--accent,#2563eb);
        outline-offset:2px;
      }

      #tracker-history-compounds .count {
        display:inline-block;
        min-width:1.5rem;
        padding:.1rem .35rem;
        border-radius:999px;
        background:rgba(127,127,127,.15);
        text-align:center;
        font-size:.8rem;
        font-weight:600;
      }

      #tracker-history-insights-summary {
        margin-top:.75rem;
        font-size:.85rem;
        opacity:.8;
      }
    `;

    document.head.appendChild(style);

    const panel = document.createElement('div');
    panel.id = 'tracker-history-insights';
    panel.className = 'card';

    const heading = document.createElement('h3');
    heading.textContent = 'Compound breakdown';

    const description = document.createElement('div');
    description.className = 'description';
    description.textContent =
      'Administration counts for the displayed history. ' +
      'Select a compound to search for it.';

    const compounds = document.createElement('div');
    compounds.id = 'tracker-history-compounds';

    const summary = document.createElement('div');
    summary.id = 'tracker-history-insights-summary';
    summary.setAttribute('role', 'status');
    summary.setAttribute('aria-live', 'polite');

    panel.append(
      heading,
      description,
      compounds,
      summary
    );

    controls.insertAdjacentElement('afterend', panel);

    function cellText(row, index) {
      const cell = row.cells[index];

      return cell
        ? cell.textContent.replace(/\s+/g, ' ').trim()
        : '';
    }

    function isVisible(row) {
      return !row.hidden &&
        getComputedStyle(row).display !== 'none';
    }

    function setSearch(value) {
      search.value = value;

      search.dispatchEvent(
        new Event('input', { bubbles:true })
      );

      search.focus();
    }

    function makeButton(label, count, handler) {
      const button = document.createElement('button');

      button.type = 'button';

      const name = document.createElement('span');
      name.textContent = label;

      const badge = document.createElement('span');
      badge.className = 'count';
      badge.textContent = String(count);

      button.append(name, badge);
      button.addEventListener('click', handler);

      return button;
    }

    /*
     * Preserve the complete loaded-history breakdown
     * for navigation even when a search is active.
     */
    const allCounts = new Map();

    rows.forEach(row => {
      const compound = cellText(row, 1) || 'Unknown';

      allCounts.set(
        compound,
        (allCounts.get(compound) || 0) + 1
      );
    });

    const sortedCompounds = Array.from(
      allCounts.entries()
    ).sort((a, b) =>
      a[0].localeCompare(b[0], undefined, {
        sensitivity:'base'
      })
    );

    function update() {
      const visible = rows.filter(isVisible);
      const visibleCounts = new Map();

      visible.forEach(row => {
        const compound = cellText(row, 1) || 'Unknown';

        visibleCounts.set(
          compound,
          (visibleCounts.get(compound) || 0) + 1
        );
      });

      compounds.replaceChildren();

      const allButton = makeButton(
        'Show All',
        rows.length,
        () => setSearch('')
      );

      compounds.appendChild(allButton);

      sortedCompounds.forEach(([compound, total]) => {
        const visibleCount = visibleCounts.get(compound) || 0;

        const button = makeButton(
          compound,
          visibleCount,
          () => setSearch(compound)
        );

        button.title =
          `${visibleCount} displayed of ${total} loaded`;

        if (!visibleCount) {
          button.style.opacity = '.5';
        }

        compounds.appendChild(button);
      });

      summary.textContent =
        `${visible.length} of ${rows.length} ` +
        'administrations displayed across ' +
        `${visibleCounts.size} compounds.`;
    }

    /*
     * Stage 34.6 updates visibility on input.
     * Queue our update afterward so counts reflect
     * the latest search results.
     */
    search.addEventListener('input', () => {
      queueMicrotask(update);
    });

    const clear = document.getElementById(
      'tracker-history-clear'
    );

    if (clear) {
      clear.addEventListener('click', () => {
        queueMicrotask(update);
      });
    }

    /*
     * Refresh compound counts when pagination
     * changes which administrations are displayed.
     */
    table.addEventListener(
      'tracker:history-page-changed',
      update
    );

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
