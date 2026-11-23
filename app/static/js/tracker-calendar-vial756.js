/* Read-only Calendar preview: changes display text, never writes doses. */
(() => {
  'use strict';
  document.addEventListener('change', event => {
    const select = event.target.closest('[data-calendar-vial-converter] select[name="vial_id"]');
    if (!select) return;
    const output = select.closest('[data-calendar-vial-converter]')
      .querySelector('[data-calendar-vial-output]');
    if (!output) return;
    const selected = select.selectedOptions[0];
    output.textContent = selected?.dataset.vialCalculation
      ? 'Calculated from this vial: ' + selected.dataset.vialCalculation
      : 'Select the physical vial to calculate syringe markings.';
  });
})();
