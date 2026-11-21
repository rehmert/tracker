/* Release 731: read-only tablet quantity previews on existing native forms.
 * Server validates and computes canonical doses; JS never submits or writes.
 */
(() => {
  'use strict';

  const fmt = value => Number(value.toFixed(3)).toString();

  function initializePanel(panel) {
    const form = panel.closest('form');
    const mode = panel.querySelector('[data-reg731-mode]');
    const manual = panel.querySelector('[data-reg731-manual]');
    const tablet = panel.querySelector('[data-reg731-tablet]');
    const strength = panel.querySelector('[data-reg731-strength]');
    const prescribed = panel.querySelector('[data-reg731-prescribed]');
    const count = panel.querySelector('[data-reg731-count]');
    const preview = panel.querySelector('[data-reg731-preview]');
    if (!form || !mode || !manual || !tablet || !strength ||
        !prescribed || !count || !preview) return;

    const item = form.querySelector('[data-reg731-item]');
    const originalKind = panel.getAttribute('data-reg731-kind') || '';
    const manualFields = Array.from(manual.querySelectorAll('input'));
    const tabletFields = [strength, prescribed, count];
    const originalManualRequired = manualFields.map(field => field.required);
    let initializedItem = item?.value ?? '';

    function itemKind() {
      if (!item) return originalKind;
      return item.selectedOptions[0]?.dataset.reg731Kind || '';
    }

    function valueFromCatalog() {
      return item?.selectedOptions[0]?.dataset.reg731Strength || '';
    }

    function previewDose() {
      const a = Number(strength.value);
      const b = Number(prescribed.value);
      const c = Number(count.value);
      if (!strength.value || !prescribed.value || !count.value ||
          !Number.isFinite(a) || !Number.isFinite(b) || !Number.isFinite(c) ||
          a <= 0 || b <= 0 || c <= 0 || c > 20 ||
          Math.abs(c * 4 - Math.round(c * 4)) > 1e-8) {
        preview.textContent = 'Enter positive tablet strength, prescribed dose, and a whole/half/quarter tablet count.';
        preview.dataset.error = 'yes';
        return;
      }
      const actual = a * c;
      const planned = panel.dataset.reg731Type === 'schedule';
      const matches = Math.abs(actual - b) < 1e-6;
      preview.textContent = fmt(c) + ' tablet' + (c === 1 ? '' : 's') +
        ' × ' + fmt(a) + ' mg = ' + fmt(actual) + ' mg. Ordered: ' +
        fmt(b) + ' mg.' +
        (planned && !matches ? ' Does not match order; correct before saving.' :
         !planned && !matches ? ' Differs from the ordered dose.' : '');
      preview.dataset.error = planned && !matches ? 'yes' : 'no';
    }

    function refresh() {
      const medication = itemKind() === 'medication';
      const tabletOption = mode.querySelector('option[value="tablet"]');
      if (tabletOption) tabletOption.disabled = !medication;
      if (!medication && mode.value === 'tablet') mode.value = 'manual';
      const useTablet = medication && mode.value === 'tablet';
      manual.hidden = useTablet;
      tablet.hidden = !useTablet;
      manualFields.forEach((field, index) => {
        field.disabled = useTablet;
        field.required = !useTablet && originalManualRequired[index];
      });
      tabletFields.forEach(field => {
        field.disabled = !useTablet;
        field.required = useTablet;
      });
      if (useTablet) previewDose();
    }

    mode.addEventListener('change', () => {
      if (mode.value === 'tablet' && !strength.value) {
        strength.value = valueFromCatalog();
      }
      refresh();
    });
    if (item) item.addEventListener('change', () => {
      if (item.value !== initializedItem) {
        initializedItem = item.value;
        strength.value = valueFromCatalog();
        prescribed.value = '';
        count.value = '0.5';
      }
      refresh();
    });
    tabletFields.forEach(field => field.addEventListener('input', previewDose));
    refresh();
  }

  function initializeDue(panel) {
    const form = panel.closest('form');
    const count = panel.querySelector('[data-reg731-count]');
    const preview = panel.querySelector('[data-reg731-preview]');
    const outcome = form?.querySelector('[name="outcome"]');
    if (!form || !count || !preview) return;
    const strength = Number(panel.dataset.reg731Strength);
    const prescribed = Number(panel.dataset.reg731Prescribed);

    function refresh() {
      if (outcome?.value === 'skipped') {
        preview.textContent = 'Skipped: no tablets recorded as taken.';
        return;
      }
      const quantity = Number(count.value);
      if (!count.value || !Number.isFinite(quantity) || quantity <= 0 ||
          quantity > 20 || Math.abs(quantity * 4 - Math.round(quantity * 4)) > 1e-8) {
        preview.textContent = 'Enter the actual number of tablets.';
        return;
      }
      preview.textContent = fmt(quantity) + ' tablet' + (quantity === 1 ? '' : 's') +
        ' = ' + fmt(strength * quantity) + ' mg taken. Ordered: ' +
        fmt(prescribed) + ' mg.';
    }
    count.addEventListener('input', refresh);
    outcome?.addEventListener('change', refresh);
    refresh();
  }

  function initialize() {
    document.querySelectorAll('[data-reg731-panel]').forEach(initializePanel);
    document.querySelectorAll('[data-reg731-due]').forEach(initializeDue);
  }
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initialize, {once: true});
  } else initialize();
})();
