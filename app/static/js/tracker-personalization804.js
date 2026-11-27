/* Release 804: reveal saved layout state without replacing existing preferences.
   Display values are browser-local; no health records or network writes. */
(() => {
  'use strict';
  function init() {
    const panel = document.getElementById('workspace-settings-panel');
    const summary = document.getElementById('tracker-preference-summary804');
    const focus = document.getElementById('tracker-focus-toggle');
    if (!panel || !summary || !focus) return;

    const selection = (selector, attribute, fallback) => {
      const chosen = panel.querySelector(selector + '[aria-pressed="true"]');
      return chosen?.getAttribute(attribute) || fallback;
    };
    function update() {
      const density = selection('[data-density-choice]', 'data-density-choice',
        document.documentElement.dataset.density || 'balanced');
      const theme = selection('[data-theme-choice]', 'data-theme-choice',
        document.documentElement.dataset.themePreference || 'light');
      const label = theme === 'system' ? 'Auto' : theme;
      const nav = focus.checked ? 'Everyday pages' : 'All pages';
      const status = summary.querySelector('strong');
      if (status) status.textContent =
        [density, label, nav].map(v => v.charAt(0).toUpperCase() + v.slice(1)).join(' · ');
    }
    panel.addEventListener('click', e => {
      if (e.target.closest('[data-density-choice],[data-theme-choice]')) queueMicrotask(update);
    });
    focus.addEventListener('change', update);
    window.addEventListener('tracker:themechange', update);
    update();
  }
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init, {once:true});
  } else init();
})();