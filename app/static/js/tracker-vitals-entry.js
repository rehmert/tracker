/* Tracker Vitals entry assistance: no database changes. */
(() => {
  'use strict';

  function initialize() {
    const form = document.querySelector(
      'form[action="/vitals"][method="post"]'
    );
    if (!form || form.dataset.entryEnhanced) return;

    const get = name => form.elements.namedItem(name);

    const when = get('measured_at');
    const weight = get('weight');
    const unit = get('weight_unit');
    const systolic = get('systolic');
    const diastolic = get('diastolic');
    const pulse = get('pulse');

    const save = form.querySelector(
      'button.primary[type="submit"]'
    );

    if (!when || !weight || !unit ||
        !systolic || !diastolic ||
        !pulse || !save) return;

    form.dataset.entryEnhanced = 'true';

    const nowButton = document.createElement('button');
    nowButton.type = 'button';
    nowButton.className = 'tracker-vitals-now';
    nowButton.textContent = 'Use Current Time';

    when.closest('label')?.append(nowButton);

    const summary = document.createElement('p');
    summary.className = 'tracker-vitals-entry-summary';
    summary.setAttribute('role', 'status');
    summary.setAttribute('aria-live', 'polite');

    const error = document.createElement('p');
    error.className = 'tracker-vitals-entry-error';
    error.id = 'tracker-vitals-entry-error';
    error.setAttribute('role', 'alert');
    error.hidden = true;

    const actions = save.parentElement;
    actions.before(summary, error);

    let submitting = false;
    const originalSaveText = save.textContent;

    function localTimestamp() {
      const date = new Date();
      const pad = number =>
        String(number).padStart(2, '0');

      return (
        date.getFullYear() + '-' +
        pad(date.getMonth() + 1) + '-' +
        pad(date.getDate()) + 'T' +
        pad(date.getHours()) + ':' +
        pad(date.getMinutes())
      );
    }

    nowButton.addEventListener('click', () => {
      when.value = localTimestamp();
      when.dispatchEvent(new Event(
        'change', { bubbles: true }
      ));
    });

    function hasValue(input) {
      return input.value.trim() !== '';
    }

    function update() {
      const values = [];

      if (hasValue(weight)) {
        values.push(
          'Weight: ' + weight.value + ' ' + unit.value
        );
      }

      const partialBP =
        hasValue(systolic) !== hasValue(diastolic);

      systolic.setCustomValidity('');
      diastolic.setCustomValidity('');

      if (
        hasValue(systolic) &&
        hasValue(diastolic)
      ) {
        values.push(
          'Blood Pressure: ' +
          systolic.value + '/' + diastolic.value
        );
      }

      if (hasValue(pulse)) {
        values.push('Pulse: ' + pulse.value + ' BPM');
      }

      if (partialBP) {
        const missing = hasValue(systolic)
          ? diastolic : systolic;

        missing.setCustomValidity(
          'Enter both blood pressure numbers.'
        );

        error.textContent =
          'Blood pressure requires both numbers.';
        error.hidden = false;
      } else {
        error.hidden = true;
        error.textContent = '';
      }

      summary.textContent = values.length
        ? 'Ready to Record: ' + values.join(' · ')
        : 'Enter at least one measurement to save.';

      return {
        partialBP,
        hasMeasurement:
          hasValue(weight) ||
          hasValue(systolic) ||
          hasValue(diastolic) ||
          hasValue(pulse)
      };
    }

    form.addEventListener('input', update);
    form.addEventListener('change', update);

    form.addEventListener('submit', event => {
      if (submitting) {
        event.preventDefault();
        return;
      }

      const state = update();

      if (!state.hasMeasurement) {
        event.preventDefault();
        error.textContent =
          'Enter weight, blood pressure or pulse.';
        error.hidden = false;
        weight.focus();
        return;
      }

      if (
        state.partialBP ||
        !form.checkValidity()
      ) {
        event.preventDefault();
        form.reportValidity();
        return;
      }

      submitting = true;
      save.disabled = true;
      save.textContent = 'Saving…';
    });

    window.addEventListener('pageshow', () => {
      submitting = false;
      save.disabled = false;
      save.textContent = originalSaveText;
      update();
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
