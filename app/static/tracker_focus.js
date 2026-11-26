(() => {
  'use strict';
  const KEY = 'tracker.navigation.focus.v1';
  // Daily destinations only. Advanced pages remain accessible by search and
  // direct URL; the current page stays in the sidebar even when advanced.
  function init() {
    const toggle = document.getElementById('tracker-focus-toggle');
    const nav = document.getElementById('nav-sortable');
    if (!toggle || !nav) return;
    // Prefer the focused sidebar for new browsers, but never override an
    // explicit preference saved by an existing user.
    let enabled = true;
    try {
      const saved = localStorage.getItem(KEY);
      if (saved !== null) enabled = saved === 'true';
    } catch (_) {}
    function apply() {
      const active = new Set();
      nav.querySelectorAll('a[aria-current="page"]').forEach(a => {
        active.add(a.getAttribute('href'));
      });
      nav.querySelectorAll('.nav-section').forEach(section => {
        let visible = 0;
        section.querySelectorAll('li[data-nav-key]').forEach(item => {
          const href = item.dataset.navKey;
          const show = !enabled || item.dataset.navPrimary === 'yes' || active.has(href);
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
