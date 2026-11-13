/* Release 602: read-only guidance for the canonical dose form.
 * Never copies amounts, submits forms, or writes inventory.
 */
(() => {
  'use strict';

  function initialize() {
    const root = document.querySelector('[data-dose-fast602]');
    const form = document.querySelector('form[hx-post="/doses"]');
    const status = root?.querySelector('[data-dose-progress602]');
    if (!root || !form || !status || root.dataset.initialized602) return;
    root.dataset.initialized602 = '1';

    const field = name => form.elements.namedItem(name);
    const value = name => String(field(name)?.value || '').trim();
    const steps = {
      vial: root.querySelector('[data-dose-step602="vial"]'),
      amount: root.querySelector('[data-dose-step602="amount"]'),
      when: root.querySelector('[data-dose-step602="when"]'),
      review: root.querySelector('[data-dose-step602="review"]')
    };

    let pending = false;

    function update() {
      pending = false;
      const vial = /^[1-9]\d*$/.test(value('vial_id'));
      const numeric = Number(value('amount'));
      const useRemaining = Boolean(field('use_remaining')?.checked);
      const amount = useRemaining ||
        (value('amount') !== '' && Number.isFinite(numeric) && numeric > 0);
      const when = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}$/.test(
        value('taken_at')
      );

      const complete = Number(vial) + Number(amount) + Number(when);
      steps.vial.dataset.complete602 = String(vial);
      steps.amount.dataset.complete602 = String(amount);
      steps.when.dataset.complete602 = String(when);

      // Review is always a deliberate human action, never marked as
      // automatically completed by entering form values.
      steps.review.dataset.complete602 = 'false';

      const message = complete === 3
        ? '3 of 3 entry details present. Review the calculation, selected vial, timestamp, and final summary before saving.'
        : complete + ' of 3 entry details present. ' +
          (!vial ? 'Choose the actual vial. ' : '') +
          (!amount ? 'Enter the actual amount. ' : '') +
          (!when ? 'Confirm the recorded time. ' : '') +
          'Final review and Save are required.';
      if (status.textContent !== message) status.textContent = message;
    }

    function schedule() {
      if (pending) return;
      pending = true;
      requestAnimationFrame(update);
    }

    form.addEventListener('input', schedule);
    form.addEventListener('change', schedule);
    form.addEventListener('reset', schedule);
    form.addEventListener('htmx:afterSettle', schedule);
    document.body.addEventListener('tracker:dose-saved', schedule);
    window.addEventListener('pageshow', schedule);
    update();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initialize, {once:true});
  } else {
    initialize();
  }
})();
