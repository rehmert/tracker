/*
 * Supply use preview.
 * No network requests or inventory mutations.
 * Server remains authoritative for stock validation.
 */
(() => {
  'use strict';

  function initialize() {
    const forms = document.querySelectorAll(
      'form[data-tracker-supply-use]'
    );

    forms.forEach(form => {
      if (form.dataset.previewReady) return;

      const input = form.querySelector(
        'input[name="quantity"]'
      );
      const button = form.querySelector(
        'button[type="submit"],button:not([type])'
      );

      const remaining = Number(
        form.dataset.remaining
      );

      if (
        !input ||
        !button ||
        !Number.isFinite(remaining)
      ) return;

      form.dataset.previewReady = 'true';

      const unit = form.dataset.unit || 'units';

      const preview = document.createElement('span');
      preview.className = 'tracker-supply-use-preview';
      preview.setAttribute('role', 'status');
      preview.setAttribute('aria-live', 'polite');

      form.append(preview);

      const format = number =>
        new Intl.NumberFormat(undefined, {
          maximumFractionDigits: 8
        }).format(number);

      function update() {
        const value = input.value.trim();

        input.setCustomValidity('');

        if (!value) {
          preview.textContent =
            'Available: ' +
            format(remaining) + ' ' + unit;
          preview.dataset.valid = 'neutral';
          return false;
        }

        const quantity = Number(value);

        if (
          !Number.isFinite(quantity) ||
          quantity <= 0
        ) {
          input.setCustomValidity(
            'Enter a positive quantity.'
          );
          preview.textContent =
            'Enter a quantity greater than zero.';
          preview.dataset.valid = 'false';
          return false;
        }

        if (quantity > remaining) {
          input.setCustomValidity(
            'Quantity exceeds remaining stock.'
          );
          preview.textContent =
            'Insufficient stock: ' +
            format(remaining) + ' ' + unit +
            ' available.';
          preview.dataset.valid = 'false';
          return false;
        }

        const after = Math.max(
          0, remaining - quantity
        );

        preview.textContent =
          'After use: ' +
          format(after) + ' ' + unit +
          ' remaining';

        preview.dataset.valid = 'true';
        return true;
      }

      let submitting = false;

      input.addEventListener('input', update);
      input.addEventListener('change', update);

      form.addEventListener('submit', event => {
        if (submitting) {
          event.preventDefault();
          return;
        }

        if (!update() || !form.checkValidity()) {
          event.preventDefault();
          form.reportValidity();
          return;
        }

        submitting = true;
        button.disabled = true;
      });

      window.addEventListener('pageshow', () => {
        submitting = false;
        button.disabled = false;
        update();
      });

      update();
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener(
      'DOMContentLoaded',
      initialize,
      { once: true }
    );
  } else {
    initialize();
  }
})();
