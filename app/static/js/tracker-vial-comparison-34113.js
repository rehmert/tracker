(() => {
  'use strict';

  function validDate(value) {
    if (!/^\d{4}-\d{2}-\d{2}$/.test(value || '')) {
      return false;
    }

    const date = new Date(value + 'T12:00:00');

    return (
      !Number.isNaN(date.getTime()) &&
      date.getFullYear() === Number(value.slice(0, 4)) &&
      date.getMonth() + 1 === Number(value.slice(5, 7)) &&
      date.getDate() === Number(value.slice(8, 10))
    );
  }

  function todayLocal() {
    const now = new Date();

    return [
      now.getFullYear(),
      String(now.getMonth() + 1).padStart(2, '0'),
      String(now.getDate()).padStart(2, '0')
    ].join('-');
  }

  function initialize() {
    const root = document.getElementById(
      'tracker-vial-comparison-34113'
    );

    if (!root) return;

    const search = document.getElementById(
      'tracker-vial-search-34113'
    );

    const filter = document.getElementById(
      'tracker-vial-filter-34113'
    );

    const results = document.getElementById(
      'tracker-vial-results-34113'
    );

    const empty = document.getElementById(
      'tracker-vial-empty-34113'
    );

    const rows = Array.from(
      root.querySelectorAll('[data-vial-row]')
    );

    const params = new URLSearchParams(
      window.location.search
    );

    const plannedDate = params.get('planned_date');

    // A scheduled administration is evaluated against
    // its scheduled date. Otherwise use the local date.
    const referenceDate = validDate(plannedDate)
      ? plannedDate
      : todayLocal();

    function updateDateStatus(row) {
      const expiration = row.dataset.vialExpires;
      const beyondUse = row.dataset.vialBeyondUse;

      const warnings = [];

      if (validDate(expiration) &&
          expiration < referenceDate) {
        warnings.push('Expired by reference date');
      }

      if (validDate(beyondUse) &&
          beyondUse < referenceDate) {
        warnings.push('Beyond-use date passed');
      }

      row.dataset.vialAttention =
        warnings.length ? '1' : '0';

      const output = row.querySelector(
        '[data-vial-date-warning]'
      );

      if (output) {
        output.hidden = warnings.length === 0;
        output.textContent = warnings.join(' · ');
      }

      row.classList.toggle(
        'tracker-vial-needs-review',
        warnings.length > 0
      );
    }

    function updateLinks() {
      const keys = [
        'planned_date',
        'planned_time',
        'planned_amount',
        'planned_unit'
      ];

      for (const link of root.querySelectorAll(
        '[data-vial-select]'
      )) {
        const url = new URL(
          link.getAttribute('href'),
          window.location.href
        );

        if (
          url.origin !== window.location.origin ||
          url.pathname !== '/doses'
        ) {
          continue;
        }

        for (const key of keys) {
          const value = params.get(key);

          if (value && !url.searchParams.has(key)) {
            url.searchParams.set(key, value);
          }
        }

        link.href = url.pathname + url.search + url.hash;
      }
    }

    function updateFilters() {
      const query = (search?.value || '')
        .trim()
        .toLocaleLowerCase();

      const mode = filter?.value || 'all';

      let count = 0;

      for (const row of rows) {
        const matchesSearch =
          !query ||
          row.textContent.toLocaleLowerCase().includes(query);

        let matchesMode = true;

        switch (mode) {
          case 'sufficient':
            matchesMode =
              row.dataset.vialState === 'sufficient' &&
              row.dataset.vialAttention !== '1';
            break;

          case 'recommended':
            matchesMode =
              row.dataset.vialRecommended === '1';
            break;

          case 'attention':
            matchesMode =
              row.dataset.vialAttention === '1' ||
              row.dataset.vialState === 'insufficient' ||
              row.dataset.vialState === 'unknown';
            break;
        }

        row.hidden = !(matchesSearch && matchesMode);

        if (!row.hidden) count++;
      }

      if (empty) {
        empty.hidden = count !== 0;
      }

      if (results) {
        results.textContent =
          `${count} of ${rows.length} vials shown` +
          ` · Date reference: ${referenceDate}`;
      }
    }

    for (const row of rows) {
      updateDateStatus(row);
    }

    updateLinks();
    updateFilters();

    search?.addEventListener('input', updateFilters);
    filter?.addEventListener('change', updateFilters);
  }

  if (document.readyState === 'loading') {
    document.addEventListener(
      'DOMContentLoaded',
      initialize,
      { once: true }
    );
  } else {
    initialize();
  }
})();
