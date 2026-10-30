(() => {
  'use strict';

  function initialize() {
    const input = document.getElementById('nav-filter');
    const results = document.getElementById('page-finder-results');
    const container = document.getElementById('page-finder-container');

    if (!input || !results || !container) return;

    let active = -1;

    function matches() {
      const query = input.value.trim().toLocaleLowerCase();
      if (!query) return [];

      const pages = [];

      document.querySelectorAll(
        '#nav-sortable .nav-section'
      ).forEach(section => {
        const category = section.dataset.section || '';

        section.querySelectorAll(
          '[data-nav-key] > a'
        ).forEach(link => {
          const name = link.textContent.trim();
          const searchable = (
            name + ' ' + category
          ).toLocaleLowerCase();

          if (searchable.includes(query)) {
            pages.push({
              name,
              category,
              href: link.getAttribute('href')
            });
          }
        });
      });

      const dashboard = {
        name: 'Dashboard',
        category: 'Overview',
        href: '/'
      };

      if ((
        dashboard.name + ' ' + dashboard.category
      ).toLocaleLowerCase().includes(query)) {
        pages.push(dashboard);
      }

      return pages.sort((a, b) =>
        a.name.localeCompare(b.name, undefined, {
          sensitivity: 'base',
          numeric: true
        })
      ).slice(0, 12);
    }

    function setActive(index) {
      const options = [...results.querySelectorAll(
        '[role="option"]'
      )];

      active = index;

      options.forEach((option, i) => {
        option.classList.toggle(
          'is-active', i === active
        );
        option.setAttribute(
          'aria-selected',
          String(i === active)
        );
      });
    }

    function render() {
      const items = matches();
      results.replaceChildren();
      active = -1;

      if (!input.value.trim()) {
        results.hidden = true;
        return;
      }

      if (!items.length) {
        const empty = document.createElement('div');
        empty.className = 'page-finder-empty';
        empty.textContent = 'No matching pages';
        results.appendChild(empty);
      }

      items.forEach(item => {
        const link = document.createElement('a');

        link.href = item.href;
        link.className = 'page-finder-result';
        link.setAttribute('role', 'option');
        link.setAttribute('aria-selected', 'false');

        const name = document.createElement('strong');
        name.textContent = item.name;

        const category = document.createElement('small');
        category.textContent = item.category;

        link.append(name, category);
        results.appendChild(link);
      });

      results.hidden = false;
    }

    input.setAttribute('aria-controls', results.id);
    input.setAttribute('aria-autocomplete', 'list');
    input.setAttribute('role', 'combobox');
    input.setAttribute('aria-expanded', 'false');

    function update() {
      render();
      input.setAttribute(
        'aria-expanded',
        String(!results.hidden)
      );
    }

    input.addEventListener('input', update);

    input.addEventListener('focus', () => {
      if (input.value.trim()) update();
    });

    input.addEventListener('keydown', event => {
      const options = [...results.querySelectorAll(
        '[role="option"]'
      )];

      if (event.key === 'Escape') {
        results.hidden = true;
        input.setAttribute('aria-expanded', 'false');
        return;
      }

      if (!options.length || results.hidden) return;

      if (event.key === 'ArrowDown') {
        event.preventDefault();
        setActive((active + 1) % options.length);
      }

      if (event.key === 'ArrowUp') {
        event.preventDefault();
        setActive(
          (active - 1 + options.length) % options.length
        );
      }

      if (event.key === 'Enter') {
        event.preventDefault();
        const selected = options[
          active >= 0 ? active : 0
        ];
        if (selected) window.location.assign(selected.href);
      }
    });

    document.addEventListener('pointerdown', event => {
      if (!container.contains(event.target)) {
        results.hidden = true;
        input.setAttribute('aria-expanded', 'false');
      }
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener(
      'DOMContentLoaded', initialize
    );
  } else {
    initialize();
  }
})();
