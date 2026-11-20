/* Release 710: one canonical dose form for ordinary and prepared physical vials.
 * Switching to a blend defaults to mL; users may explicitly select an
 * applicable mass/IU unit for a single-compound blend. Never auto-submit.
 */
(() => {
  'use strict';
  function initialize() {
    const form = document.querySelector('form[hx-post="/doses"]');
    const source = form?.querySelector('select[name="vial_id"]');
    const unit = form?.querySelector('select[name="unit"]');
    if (!source || !unit) return;
    let previous = '';
    function update() {
      const chosen = source.value;
      const blend = /^blend:[1-9]\d*$/.test(chosen);
      const switched = chosen !== previous;
      if (blend && switched && !['mL', 'uL'].includes(unit.value)) {
        unit.value = 'mL';
        unit.dispatchEvent(new Event('change', {bubbles:true}));
      }
      previous = chosen;
    }
    source.addEventListener('change', update);
    form.addEventListener('reset', () => { previous = ''; });
    update();
  }
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initialize, {once:true});
  } else {
    initialize();
  }
})();
