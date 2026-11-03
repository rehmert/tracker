/*
 * Quick Entry action finder.
 * Navigation only; no network, storage, or record writes.
 */
(() => {
  'use strict';

  function initialize() {
    const root = document.querySelector(
      '[data-quick-entry]'
    );

    if (!root || root.dataset.ready) return;

    const search = root.querySelector(
      '[data-quick-search]'
    );
    const reset = root.querySelector(
      '[data-quick-reset]'
    );
    const count = root.querySelector(
      '[data-quick-count]'
    );
    const empty = root.querySelector(
      '[data-quick-empty]'
    );
    const tabs = Array.from(root.querySelectorAll(
      'button[data-quick-category]'
    ));
    const actions = Array.from(root.querySelectorAll(
      'a[data-quick-action]'
    ));

    if (!search || !reset || !count ||
        !empty || !tabs.length) return;

    root.dataset.ready = 'true';
    let category = 'all';

    function update() {
      const words = search.value
        .trim()
        .toLocaleLowerCase()
        .split(/\s+/)
        .filter(Boolean);

      let visible = 0;

      actions.forEach(action => {
        const inCategory =
          category === 'all' ||
          action.dataset.quickCategory === category;

        const searchable = (
          action.textContent + ' ' +
          (action.dataset.quickKeywords || '')
        ).toLocaleLowerCase();

        const matches = words.every(
          word => searchable.includes(word)
        );

        const show = inCategory && matches;
        action.hidden = !show;
        if (show) visible++;
      });

      tabs.forEach(tab => {
        tab.setAttribute(
          'aria-pressed',
          String(tab.dataset.quickCategory === category)
        );
      });

      count.textContent =
        'Showing ' + visible +
        ' of ' + actions.length + ' actions';

      empty.hidden = visible !== 0;
    }

    search.addEventListener('input', update);

    search.addEventListener('keydown', event => {
      if (event.key === 'Escape') {
        event.preventDefault();
        search.value = '';
        update();
        return;
      }

      const visible = actions.filter(
        action => !action.hidden
      );

      if (
        event.key === 'ArrowDown' &&
        visible.length
      ) {
        event.preventDefault();
        visible[0].focus();
        return;
      }

      // Only navigate automatically when the
      // search has one unambiguous result.
      if (
        event.key === 'Enter' &&
        visible.length === 1
      ) {
        event.preventDefault();
        window.location.assign(visible[0].href);
      }
    });

    tabs.forEach(tab => {
      tab.addEventListener('click', () => {
        category = tab.dataset.quickCategory;
        update();
      });
    });

    reset.addEventListener('click', () => {
      search.value = '';
      category = 'all';
      update();
      search.focus();
    });

    document.addEventListener('keydown', event => {
      if (
        event.key !== '/' ||
        event.ctrlKey ||
        event.altKey ||
        event.metaKey ||
        event.isComposing
      ) return;

      const target = event.target;
      if (
        target instanceof HTMLElement &&
        (
          target.isContentEditable ||
          ['INPUT', 'TEXTAREA', 'SELECT'].includes(
            target.tagName
          )
        )
      ) return;

      event.preventDefault();
      search.focus();
    });

    update();
  }

  if (document.readyState === 'loading') {
    document.addEventListener(
      'DOMContentLoaded', initialize, { once: true }
    );
  } else {
    initialize();
  }
})();
