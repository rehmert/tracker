/* Refresh the one-use dose token after a successful HTMX response.
 * The server fires tracker:dose-saved only after commit and after the
 * existing form-reset handler runs. No automatic dose submission.
 */
(() => {
  'use strict';

  function initialize() {
    const form = document.querySelector('form[hx-post="/doses"]');
    if (!form) return;

    form.addEventListener('tracker:dose-saved', (event) => {
      const data = event.detail || {};
      const token = form.querySelector('input[name="submission_token"]');
      const time = form.querySelector('input[name="taken_at"]');
      const status = document.getElementById('dose-sequential-status');

      // Missing/invalid token: do not permit an accidental repeat submission.
      if (!token || typeof data.submission_token !== 'string' ||
          !/^[0-9a-f-]{36}$/i.test(data.submission_token)) {
        if (status) status.textContent =
          'Entry recorded. Refresh this page before logging another.';
        const submit = form.querySelector('button[type="submit"]');
        if (submit) submit.disabled = true;
        return;
      }

      token.defaultValue = data.submission_token;
      token.value = data.submission_token;

      // Use a new local time, never the historical time from a copied entry.
      if (time && typeof data.new_time === 'string' &&
          /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}$/.test(data.new_time)) {
        time.defaultValue = data.new_time;
        time.value = data.new_time;
      }
      // Deliberately clear dose amount. A repeated amount is never implied
      // by a previous record or an earlier calendar handoff.
      const amount = form.querySelector('input[name="amount"]');
      if (amount) {
        amount.defaultValue = '0';
        amount.value = '0';
      }
      if (status) {
        status.textContent =
          'Entry recorded. Enter the next actual amount and review all details.';
      }
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initialize, { once: true });
  } else {
    initialize();
  }
})();
