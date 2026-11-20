/* Release 710: ordinary and prepared physical vials share the dose form.
 * A source change invalidates the prior amount and "use all" choice.
 * Never reinterpret a planned mg/IU amount as mL on initial page load.
 */
(() => {
  'use strict';
  function initialize() {
    const form = document.querySelector('form[hx-post="/doses"]');
    const source = form?.querySelector('select[name="vial_id"]');
    const unit = form?.querySelector('select[name="unit"]');
    const amount = form?.querySelector('input[name="amount"]');
    const remaining = form?.querySelector('input[name="use_remaining"]');
    if (!source || !unit) return;
    let previous = source.value;

    source.addEventListener('change', () => {
      if (source.value === previous) return;
      previous = source.value;
      // The concentration and composition may be different. Requiring a
      // fresh entry avoids carrying an unsafe quantity across physical vials.
      if (amount) {
        amount.value = '';
        amount.dispatchEvent(new Event('input', {bubbles: true}));
      }
      if (remaining) {
        remaining.checked = false;
        remaining.dispatchEvent(new Event('change', {bubbles: true}));
      }
      if (/^blend:[1-9]\d*$/.test(source.value) &&
          !['mL', 'uL', 'units'].includes(unit.value)) {
        unit.value = 'mL';
        unit.dispatchEvent(new Event('change', {bubbles: true}));
      }
    });
    form.addEventListener('reset', () => { previous = source.value; });
  }
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initialize, {once:true});
  } else {
    initialize();
  }
})();
