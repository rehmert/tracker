(() => {
  'use strict';
  const KEY = 'tracker.navigation.focus.v1';
  const ESSENTIAL = new Set([
    '/', '/workflow-hub', '/activity', '/calendar', '/quick-entry',
    '/protocols', '/doses', '/dose-workspace', '/pk', '/vials',
    '/compounds', '/purchases', '/supplies', '/coas', '/vitals',
    '/labs', '/reports', '/backups'
  ]);
  function init() {
    const toggle = document.getElementById('tracker-focus-toggle');
    const nav = document.getElementById('nav-sortable');
    if (!toggle || !nav) return;
    let enabled = false;
    try { enabled = localStorage.getItem(KEY) === 'true'; } catch (_) {}
    function apply() {
      const active = new Set();
      nav.querySelectorAll('a[aria-current="page"]').forEach(a => {
        active.add(a.getAttribute('href'));
      });
      nav.querySelectorAll('.nav-section').forEach(section => {
        let visible = 0;
        section.querySelectorAll('li[data-nav-key]').forEach(item => {
          const href = item.dataset.navKey;
          const show = !enabled || ESSENTIAL.has(href) || active.has(href);
          item.classList.toggle('tracker-focus-hidden', !show);
          if (show) visible++;
        });
        section.classList.toggle('tracker-focus-hidden', visible === 0);
      });
      toggle.checked = enabled;
    }
    toggle.addEventListener('change', () => {
      enabled = toggle.checked;
      try { localStorage.setItem(KEY, String(enabled)); } catch (_) {}
      apply();
    });
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
