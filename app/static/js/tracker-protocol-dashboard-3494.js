(() => {
  'use strict';

  const STORAGE_KEY = 'tracker.protocols.filters.v1';

  function safeRead() {
    try {
      return JSON.parse(
        localStorage.getItem(STORAGE_KEY) || '{}'
      );
    } catch {
      return {};
    }
  }

  function safeSave(value) {
    try {
      localStorage.setItem(
        STORAGE_KEY,
        JSON.stringify(value)
      );
    } catch {
      // Browser storage is optional.
    }
  }

  function normalize(value) {
    return String(value || '')
      .trim()
      .toLocaleLowerCase();
  }

  function setupProtocols() {
    const toolbar = document.querySelector(
      '[data-tracker-protocol-tools]'
    );

    const table = document.querySelector(
      '[data-tracker-protocol-table]'
    );

    if (!toolbar || !table || !table.tBodies.length) {
      return;
    }

    const search = toolbar.querySelector(
      '[data-protocol-search]'
    );

    const status = toolbar.querySelector(
      '[data-protocol-status]'
    );

    const sort = toolbar.querySelector(
      '[data-protocol-sort]'
    );

    const reset = toolbar.querySelector(
      '[data-protocol-reset]'
    );

    const count = toolbar.querySelector(
      '[data-protocol-count]'
    );

    const tbody = table.tBodies[0];

    const rows = Array.from(tbody.rows).filter(
      row => row.querySelector('a[href^="/protocols/"]')
    );

    if (!rows.length) {
      toolbar.hidden = true;
      return;
    }

    const original = new Map(
      rows.map((row, index) => [row, index])
    );

    const saved = safeRead();

    const allowedStatuses = new Set([
      'all', 'active', 'what-if'
    ]);

    const allowedSorts = new Set([
      'original', 'name-asc', 'name-desc',
      'items-desc', 'items-asc'
    ]);

    search.value =
      typeof saved.search === 'string'
        ? saved.search
        : '';

    status.value = allowedStatuses.has(saved.status)
      ? saved.status
      : 'all';

    sort.value = allowedSorts.has(saved.sort)
      ? saved.sort
      : 'original';

    function name(row) {
      return normalize(row.cells[0]?.textContent);
    }

    function itemCount(row) {
      const value = Number(
        (row.cells[2]?.textContent || '')
          .replace(/,/g, '')
          .trim()
      );

      return Number.isFinite(value) ? value : 0;
    }

    function compare(a, b) {
      switch (sort.value) {
        case 'name-asc':
          return name(a).localeCompare(name(b));

        case 'name-desc':
          return name(b).localeCompare(name(a));

        case 'items-desc':
          return itemCount(b) - itemCount(a);

        case 'items-asc':
          return itemCount(a) - itemCount(b);

        default:
          return original.get(a) - original.get(b);
      }
    }

    function apply() {
      const query = normalize(search.value);

      const ordered = [...rows].sort((a, b) =>
        compare(a, b) ||
        original.get(a) - original.get(b)
      );

      let visible = 0;

      for (const row of ordered) {
        const rowStatus = normalize(
          row.cells[1]?.textContent
        );

        const matchesStatus =
          status.value === 'all' ||
          (status.value === 'active' &&
            rowStatus === 'active') ||
          (status.value === 'what-if' &&
            rowStatus === 'what-if');

        const matchesSearch =
          !query ||
          normalize(row.textContent).includes(query);

        row.hidden = !(
          matchesStatus && matchesSearch
        );

        if (!row.hidden) visible++;

        tbody.appendChild(row);
      }

      count.textContent =
        `${visible} of ${rows.length} protocols`;

      safeSave({
        search: search.value,
        status: status.value,
        sort: sort.value
      });
    }

    search.addEventListener('input', apply);
    status.addEventListener('change', apply);
    sort.addEventListener('change', apply);

    reset.addEventListener('click', () => {
      search.value = '';
      status.value = 'all';
      sort.value = 'original';

      apply();
      search.focus();
    });

    apply();
  }

  function setupDashboard() {
    const section = document.querySelector(
      '[data-dashboard-panel="2"]'
    );

    const toolbar = document.querySelector(
      '[data-tracker-schedule-tools]'
    );

    if (!section || !toolbar) return;

    const search = toolbar.querySelector(
      '[data-schedule-search]'
    );

    const reset = toolbar.querySelector(
      '[data-schedule-reset]'
    );

    const count = toolbar.querySelector(
      '[data-schedule-count]'
    );

    const cards = Array.from(
      section.querySelectorAll('.today-card')
    );

    // Only filter the scheduled/recorded activity
    // cards, not inventory forecasts.
    const targetCards = cards.filter(card => {
      const title = normalize(
        card.querySelector('h3')?.textContent
      );

      return (
        title.includes("administrations") ||
        title.includes("upcoming") ||
        title.includes("recently recorded")
      );
    });

    const entries = targetCards.flatMap(card =>
      Array.from(card.querySelectorAll('li'))
    );

    if (!entries.length) {
      toolbar.hidden = true;
      return;
    }

    function apply() {
      const query = normalize(search.value);
      let visible = 0;

      for (const entry of entries) {
        const matches =
          !query ||
          normalize(entry.textContent).includes(query);

        entry.hidden = !matches;

        if (matches) visible++;
      }

      count.textContent =
        `${visible} of ${entries.length} entries`;

      for (const card of targetCards) {
        const list = card.querySelector('ul');

        if (!list) continue;

        let message = card.querySelector(
          '[data-schedule-empty]'
        );

        const hasVisible = Array.from(
          list.querySelectorAll('li')
        ).some(item => !item.hidden);

        if (!message) {
          message = document.createElement('p');
          message.className = 'note';
          message.dataset.scheduleEmpty = '1';
          message.textContent =
            'No entries match the current search.';
          message.hidden = true;
          list.insertAdjacentElement(
            'afterend',
            message
          );
        }

        message.hidden = hasVisible || !query;
      }
    }

    search.addEventListener('input', apply);

    reset.addEventListener('click', () => {
      search.value = '';
      apply();
      search.focus();
    });

    apply();
  }

  function initialize() {
    setupProtocols();
    setupDashboard();
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
