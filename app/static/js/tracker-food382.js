document.addEventListener('DOMContentLoaded', () => {
  'use strict';

  const sections = Array.from(
    document.querySelectorAll('details.food382-accordion')
  );

  if (!sections.length) return;

  function expand(section, scroll = true) {
    if (!section) return;

    section.open = true;

    if (scroll) {
      section.scrollIntoView({
        behavior: 'smooth',
        block: 'start'
      });
    }
  }

  // Tapping a navigation shortcut opens the corresponding
  // collapsed section before scrolling to it.
  document.querySelectorAll('a[href^="#food-"]').forEach(link => {
    link.addEventListener('click', event => {
      const id = link.getAttribute('href').slice(1);
      const target = document.getElementById(id);

      if (!target || !target.matches('details.food382-accordion')) {
        return;
      }

      event.preventDefault();
      expand(target);

      if (history.replaceState) {
        history.replaceState(null, '', '#' + id);
      }
    });
  });

  // A submitted saved-food search reloads the page.
  // Reopen that section so search results are immediately visible.
  const query = new URLSearchParams(location.search).get('q');

  if (query) {
    expand(document.getElementById('food-search'), false);
  }

  // Honor bookmarked section links.
  const hash = decodeURIComponent(
    location.hash.replace(/^#/, '')
  );

  if (hash) {
    const target = document.getElementById(hash);

    if (target?.matches('details.food382-accordion')) {
      expand(target, false);
    }
  }

  // Selecting an external database result populates fields
  // inside the Add Food form. Open the containing accordion
  // before the older lookup script attempts to scroll/focus.
  const addFood = document.getElementById('food-add');
  const searchResults = document.getElementById('food380-results');

  if (addFood && searchResults) {
    searchResults.addEventListener('click', event => {
      const chosen = event.target.closest('button');

      if (chosen && chosen.textContent.trim() === 'Use Food') {
        expand(addFood, false);
      }
    }, true);
  }

  // If the user arrives with a form validation/error hash
  // targeting a descendant, reveal its enclosing accordion.
  if (hash) {
    const target = document.getElementById(hash);
    const enclosing = target?.closest(
      'details.food382-accordion'
    );

    if (enclosing) {
      expand(enclosing, false);
    }
  }
});
