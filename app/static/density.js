/* Browser-local display density; applies before styles render. */
(() => {
  const KEY = 'tracker-density';
  const choices = ['comfortable', 'balanced', 'compact'];
  function get() {
    try { const value = localStorage.getItem(KEY); return choices.includes(value) ? value : 'balanced'; }
    catch (_) { return 'balanced'; }
  }
  function apply(value) {
    document.documentElement.dataset.density = value;
    document.querySelectorAll('[data-density-choice]').forEach(button => {
      button.setAttribute('aria-pressed', String(button.dataset.densityChoice === value));
    });
  }
  window.TrackerDensity = {
    get,
    set(value) {
      if (!choices.includes(value)) return;
      try { localStorage.setItem(KEY, value); } catch (_) { /* private browsing */ }
      apply(value);
    }
  };
  apply(get());
  document.addEventListener('DOMContentLoaded', () => {
    apply(get());
    document.querySelectorAll('[data-density-choice]').forEach(button => {
      button.addEventListener('click', () => window.TrackerDensity.set(button.dataset.densityChoice));
    });
  });
})();
