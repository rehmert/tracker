(() => {
  'use strict';

  function initialize() {
    const controls = document.getElementById(
      'timeline-filters'
    );

    if (!controls) return;

    const rows = [
      ...document.querySelectorAll(
        'tr.timeline-event'
      )
    ];

    const category = document.getElementById(
      'timeline-category'
    );

    const search = document.getElementById(
      'timeline-search'
    );

    const clear = document.getElementById(
      'timeline-clear'
    );

    const count = document.getElementById(
      'timeline-count'
    );

    const categories = [
      ...new Set(
        rows.map(row =>
          row.dataset.category
        ).filter(Boolean)
      )
    ].sort((a, b) => a.localeCompare(b));

    for (const value of categories) {
      const option = document.createElement(
        'option'
      );

      option.value = value;
      option.textContent = value;

      category.appendChild(option);
    }

    function update() {
      const term = search.value
        .trim()
        .toLowerCase();

      let visible = 0;

      for (const row of rows) {
        const matchesCategory =
          !category.value ||
          row.dataset.category === category.value;

        const matchesText =
          !term ||
          row.textContent
            .toLowerCase()
            .includes(term);

        row.hidden = !(
          matchesCategory &&
          matchesText
        );

        if (!row.hidden) {
          visible++;
        }
      }

      count.textContent =
        `${visible} of ${rows.length} events`;
    }

    category.addEventListener(
      'change',
      update
    );

    search.addEventListener(
      'input',
      update
    );

    clear.addEventListener(
      'click',
      () => {
        category.value = '';
        search.value = '';
        update();
      }
    );

    update();
  }

  if (document.readyState === 'loading') {
    document.addEventListener(
      'DOMContentLoaded',
      initialize
    );
  } else {
    initialize();
  }
})();
