/*
 * Quick Entry metric-specific deep links.
 * Focus only explicitly named Vitals inputs.
 * Does not change or submit form values.
 */
(() => {
  'use strict';

  const allowed = new Set([
    'quick-vitals-weight',
    'quick-vitals-bp',
    'quick-vitals-pulse'
  ]);

  function focusRequestedInput() {
    const id = window.location.hash.slice(1);
    if (!allowed.has(id)) return;

    const input = document.getElementById(id);
    if (!input) return;

    if (
      input.form?.dataset.trackerVitalsEntry
      !== 'create'
    ) return;

    input.focus({ preventScroll: true });
    input.scrollIntoView({
      block: 'center',
      behavior: 'auto'
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener(
      'DOMContentLoaded',
      focusRequestedInput,
      { once: true }
    );
  } else {
    focusRequestedInput();
  }

  window.addEventListener(
    'hashchange',
    focusRequestedInput
  );
})();
