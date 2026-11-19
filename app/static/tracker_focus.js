/* Release 694: everyday sidebar by default; preserve user opt-out and every route. */
(() => {
  'use strict';
  const KEY = 'tracker.navigation.focus.v1';
  // A concise daily navigation; every other page remains reachable through
  // the Show all pages control and the existing page finder/search.
  const ESSENTIAL = new Set([
    '/', '/mobile', '/calendar', '/quick-entry', '/doses',
    '/dose-workspace', '/protocols', '/pk', '/vials', '/purchases',
    '/coas', '/vitals', '/workouts', '/food', '/regimen',
    '/labs', '/health-insights', '/backups'
  ]);

  function init() {
    const toggle = document.getElementById('tracker-focus-toggle');
    const sidebar = document.getElementById('tracker-focus-sidebar-toggle');
    const nav = document.getElementById('nav-sortable');
    const filter = document.getElementById('nav-filter');
    if (!toggle || !nav) return;

    // Existing browser choices win. Only a new/empty browser profile adopts
    // the everyday default. Storage-blocked browsers get the same safe view.
    let enabled = true;
    try {
      const saved = localStorage.getItem(KEY);
      if (saved !== null) enabled = saved === 'true';
    } catch (_) {}

    function apply() {
      // Searching must expose matching advanced destinations even when
      // Everyday mode is active; otherwise results appear hidden in sidebar.
      const query = (filter?.value || '').trim().toLocaleLowerCase();
      const active = new Set();
      nav.querySelectorAll('a[aria-current="page"]').forEach(a => {
        active.add(a.getAttribute('href'));
      });
      nav.querySelectorAll('.nav-section').forEach(section => {
        let visible = 0;
        section.querySelectorAll('li[data-nav-key]').forEach(item => {
          const href = item.dataset.navKey;
          const label = item.querySelector('a')?.textContent.toLocaleLowerCase() || '';
          const heading = section.dataset.section?.toLocaleLowerCase() || '';
          const matchesSearch = Boolean(query) &&
            (label.includes(query) || heading.includes(query));
          const show = !enabled || ESSENTIAL.has(href) ||
            active.has(href) || matchesSearch;
          item.classList.toggle('tracker-focus-hidden', !show);
          if (show) visible++;
        });
        section.classList.toggle('tracker-focus-hidden', visible === 0);
      });
      toggle.checked = enabled;
      if (sidebar) {
        sidebar.textContent = enabled ? 'Show all pages' : 'Show everyday pages';
        sidebar.setAttribute('aria-expanded', String(!enabled));
      }
    }

    function setEnabled(value) {
      enabled = value;
      try { localStorage.setItem(KEY, String(enabled)); } catch (_) {}
      apply();
    }

    toggle.addEventListener('change', () => setEnabled(toggle.checked));
    sidebar?.addEventListener('click', () => setEnabled(!enabled));
    filter?.addEventListener('input', apply);
    apply();

    // Existing sidebar preferences may reorder links; reapply only on changes
    // to the navigation structure, not to class/style attributes.
    const observer = new MutationObserver(records => {
      if (records.some(record => record.type === 'childList')) apply();
    });
    observer.observe(nav, {childList: true, subtree: true});
  }
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init, {once: true});
  } else init();
})();
