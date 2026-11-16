/* Release 646: progressively enhance the native COA test-type selects.
 * The catalog choices work without JS; custom entry appears on demand.
 */
(() => {
  "use strict";
  function setup(form) {
    const select = form.querySelector("[data-coa-test-type-select]");
    const wrapper = form.querySelector("[data-coa-custom-container]");
    const field = wrapper?.querySelector('input[name="custom_test_type"]');
    if (!select || !wrapper || !field) return;
    const refresh = () => {
      const custom = select.value === "__custom__";
      wrapper.hidden = !custom;
      field.disabled = !custom;
      field.required = custom;
      if (custom) field.focus();
    };
    select.addEventListener("change", refresh);
    const custom = select.value === "__custom__";
    wrapper.hidden = !custom;
    field.disabled = !custom;
    field.required = custom;
  }
  document.querySelectorAll("[data-coa-test-type-form]").forEach(setup);
})();
