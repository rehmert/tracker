/*
 * Tracker Stage 28
 * Read-only browser sorting and vial search.
 */

(() => {
  'use strict';

  function init() {
    const input = document.getElementById('tracker-vial-search');
    const container = document.getElementById('tracker-available-vials');

    if (!input || !container) return;

    const table = container.querySelector(
      '[data-tracker-sortable-vials]'
    );

    if (!table) return;

    const tbody = table.querySelector('tbody');

    const rows = Array.from(
      tbody.querySelectorAll('[data-tracker-vial-row]')
    );

    const headers = Array.from(
      table.querySelectorAll('[data-tracker-sort-key]')
    );

    const count = document.getElementById('tracker-vial-count');
    const empty = document.getElementById('tracker-vial-no-matches');
    const clear = document.getElementById('tracker-vial-clear');
    const reset = document.getElementById('tracker-vial-reset');

    const limitSelect = document.getElementById(
      'tracker-vial-display-limit'
    );

    const preferenceKey = 'tracker.workspace.vialDisplayLimit';

    let displayLimit = 5;

    try {
      const saved = localStorage.getItem(preferenceKey);
      if (['3', '5', '10', 'all'].includes(saved)) {
        displayLimit = saved === 'all' ? Infinity : Number(saved);
      }
    } catch (_) {
      // Private browsing or disabled storage: use the default.
    }

    if (limitSelect) {
      limitSelect.value = displayLimit === Infinity
        ? 'all'
        : String(displayLimit);
    }

    let sortKey = 'recommended';
    let direction = 'asc';

    function getValue(row, key) {
      const property = key.replace(
        /-([a-z])/g,
        (_, letter) => letter.toUpperCase()
      );

      return row.dataset['tracker' + property.charAt(0).toUpperCase() + property.slice(1)] || '';
    }

    function compare(a, b) {
      if (sortKey === 'recommended') {
        const av = Number(getValue(a, 'recommended'));
        const bv = Number(getValue(b, 'recommended'));

        if (av !== bv) return bv - av;
      } else if (sortKey === 'remaining') {
        const av = Number(getValue(a, 'remaining'));
        const bv = Number(getValue(b, 'remaining'));

        if (av !== bv) {
          return direction === 'asc'
            ? av - bv
            : bv - av;
        }
      } else {
        const av = getValue(a, sortKey);
        const bv = getValue(b, sortKey);

        const dateKey = [
          'first-used',
          'beyond-use',
          'expires'
        ].includes(sortKey);

        if (dateKey && !av && bv) return 1;
        if (dateKey && av && !bv) return -1;

        const result = av.localeCompare(
          bv,
          undefined,
          { numeric: true, sensitivity: 'base' }
        );

        if (result !== 0) {
          return direction === 'asc'
            ? result
            : -result;
        }
      }

      return Number(getValue(a, 'id')) -
             Number(getValue(b, 'id'));
    }

    function sortRows() {
      rows.sort(compare);

      const fragment = document.createDocumentFragment();

      rows.forEach(row => fragment.appendChild(row));

      tbody.appendChild(fragment);

      headers.forEach(header => {
        const active =
          header.dataset.trackerSortKey === sortKey;

        header.setAttribute(
          'aria-sort',
          active
            ? (direction === 'asc'
                ? 'ascending'
                : 'descending')
            : 'none'
        );
      });
    }

    function priorityCompare(a, b) {
      const recommendedA = a.dataset.trackerRecommended === '1';
      const recommendedB = b.dataset.trackerRecommended === '1';

      if (recommendedA !== recommendedB) {
        return recommendedA ? -1 : 1;
      }

      const activeA = a.dataset.trackerStatus === 'in_use';
      const activeB = b.dataset.trackerStatus === 'in_use';

      if (activeA !== activeB) {
        return activeA ? -1 : 1;
      }

      const expiryA = a.dataset.trackerExpires || '';
      const expiryB = b.dataset.trackerExpires || '';

      if (expiryA !== expiryB) {
        if (!expiryA) return 1;
        if (!expiryB) return -1;
        return expiryA.localeCompare(expiryB);
      }

      const ageA =
        a.dataset.trackerPurchaseDate ||
        a.dataset.trackerReceivedDate ||
        a.dataset.trackerCreatedDate ||
        '';

      const ageB =
        b.dataset.trackerPurchaseDate ||
        b.dataset.trackerReceivedDate ||
        b.dataset.trackerCreatedDate ||
        '';

      if (ageA !== ageB) {
        if (!ageA) return 1;
        if (!ageB) return -1;
        return ageA.localeCompare(ageB);
      }

      return Number(a.dataset.trackerId) -
             Number(b.dataset.trackerId);
    }

    function update() {
      const query = input.value.trim().toLocaleLowerCase();

      // Group by actual compound ID and labeled vial strength.
      // Searching temporarily reveals all matching inventory.
      const groups = new Map();

      rows.forEach(row => {
        const key = [
          row.dataset.trackerCompoundId,
          row.dataset.trackerStrength
        ].join('|');

        if (!groups.has(key)) groups.set(key, []);
        groups.get(key).push(row);
      });

      const allowed = new Set();

      groups.forEach(group => {
        group.sort(priorityCompare);

        const maximum = query || displayLimit === Infinity
          ? group.length
          : displayLimit;

        group.slice(0, maximum).forEach(row => allowed.add(row));
      });

      let visible = 0;
      let matching = 0;

      rows.forEach(row => {
        const matchesSearch =
          !query ||
          row.textContent.toLocaleLowerCase().includes(query);

        if (matchesSearch) matching++;

        const show = matchesSearch && allowed.has(row);

        row.hidden = !show;

        if (show) visible++;
      });

      if (count) {
        const hiddenCount = rows.length - visible;

        count.textContent =
          `${visible} of ${rows.length} vials shown` +
          (hiddenCount && !query
            ? ` · ${hiddenCount} hidden by display limit`
            : '');
      }

      if (empty) {
        empty.hidden = matching !== 0;
      }

      if (clear) clear.hidden = !query;
    }

    function resetSearch() {
      input.value = '';
      update();
      input.focus();
    }

    headers.forEach(header => {
      const button = header.querySelector('button');

      if (!button) return;

      button.addEventListener('click', () => {
        const key = header.dataset.trackerSortKey;

        if (sortKey === key) {
          direction =
            direction === 'asc' ? 'desc' : 'asc';
        } else {
          sortKey = key;
          direction = 'asc';
        }

        sortRows();
        update();
      });
    });

    if (limitSelect) {
      limitSelect.addEventListener('change', () => {
        displayLimit = limitSelect.value === 'all'
          ? Infinity
          : Number(limitSelect.value);

        try {
          localStorage.setItem(
            preferenceKey,
            limitSelect.value
          );
        } catch (_) {
          // Preference remains active for this page.
        }

        update();
      });
    }

    input.addEventListener('input', update);

    if (clear) clear.addEventListener('click', resetSearch);
    if (reset) reset.addEventListener('click', resetSearch);

    sortRows();
    update();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
