/* Release 629: keep selector and explicit removal checkboxes consistent.
   All consolidation stays server-validated and requires a user submit. */
(() => {
  "use strict";
  function init() {
    document.querySelectorAll("form.food630-resolve").forEach(form => {
      form.addEventListener("submit", event => {
        if (!window.confirm(form.dataset.confirm || "Resolve these saved foods?")) {
          event.preventDefault();
        }
      });
    });
    document.querySelectorAll("form.food629-merge").forEach(form => {
      const keep = form.querySelector('select[name="keep_id"]');
      const boxes = [...form.querySelectorAll('input[name="remove_id"]')];
      if (!keep || !boxes.length) return;
      function sync() {
        for (const box of boxes) {
          box.disabled = box.value === keep.value;
          if (box.disabled) box.checked = false;
        }
      }
      keep.addEventListener("change", () => {
        for (const box of boxes) box.checked = box.value !== keep.value;
        sync();
      });
      sync();
      form.addEventListener("submit", event => {
        const remove = boxes.filter(box => !box.disabled && box.checked);
        if (!remove.length) {
          event.preventDefault();
          return;
        }
        if (!window.confirm(
          "Consolidate " + remove.length + " equivalent saved-food " +
          (remove.length === 1 ? "version" : "versions") +
          " into version #" + keep.value + "? " +
          "Existing logged meals and meal templates will point to the kept version."
        )) event.preventDefault();
      });
    });
  }
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init, {once:true});
  } else init();
})();
