/* Local-only appearance preference; no network calls or cookies. */
(() => {
  const KEY = 'tracker-theme';
  const valid = ['light', 'dark', 'system'];
  const media = window.matchMedia('(prefers-color-scheme: dark)');
  const stored = () => {
    try { const value = localStorage.getItem(KEY); return valid.includes(value) ? value : 'light'; }
    catch (_) { return 'light'; }
  };
  const apply = (choice) => {
    const actual = choice === 'system' ? (media.matches ? 'dark' : 'light') : choice;
    document.documentElement.dataset.theme = actual;
    document.documentElement.style.colorScheme = actual;
    document.documentElement.dataset.themePreference = choice;
    document.querySelectorAll('[data-theme-choice]').forEach(el => {
      el.setAttribute('aria-pressed', String(el.dataset.themeChoice === choice));
    });
    window.dispatchEvent(new CustomEvent('tracker:themechange', {detail: {theme: actual, preference: choice}}));
  };
  window.TrackerTheme = {
    set(choice) {
      if (!valid.includes(choice)) return;
      try { localStorage.setItem(KEY, choice); } catch (_) { /* private mode */ }
      apply(choice);
    },
    get: stored
  };
  apply(stored());
  media.addEventListener?.('change', () => { if (stored() === 'system') apply('system'); });
  document.addEventListener('DOMContentLoaded', () => {
    apply(stored());
    document.querySelectorAll('[data-theme-choice]').forEach(el => {
      el.addEventListener('click', () => window.TrackerTheme.set(el.dataset.themeChoice));
    });
  });
})();
