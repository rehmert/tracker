/* Browser-local workspace preferences; no backend changes. */
(() => {
  "use strict";
  function init() {
    const checks = [
      ...document.querySelectorAll("[data-pk-toggle]")
    ];

    checks.forEach(control => {
      const key = control.dataset.pkToggle;
      try {
        const saved = localStorage.getItem(
          "tracker-pk-panel-"+key
        );
        if(saved !== null)
          control.checked = saved === "true";
      } catch(_) {}

      const apply = () => {
        const panel = document.querySelector(
          '[data-pk-panel="'+key+'"]'
        );
        if(panel) panel.hidden = !control.checked;
      };

      control.addEventListener("change",() => {
        apply();
        try {
          localStorage.setItem(
            "tracker-pk-panel-"+key,
            String(control.checked)
          );
        } catch(_) {}
      });
      apply();
    });
  }

  if(document.readyState==="loading")
    document.addEventListener(
      "DOMContentLoaded",init,{once:true}
    );
  else init();
})();
