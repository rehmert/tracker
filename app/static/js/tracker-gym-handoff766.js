/* Release 766: protect unsaved set edits when switching machines. */
(() => {
  "use strict";
  function init() {
    const root = document.getElementById("workout659-root");
    const form = document.getElementById("workout659-log-form");
    const nav = document.querySelector(".workout766-handoff");
    const status = document.getElementById("workout766-connection");
    if (!root || !nav) return;
    function updateConnection() {
      if (status) status.textContent = navigator.onLine
        ? "Online · only Save Set records a set"
        : "Offline · save a local set draft or use the existing offline queue";
    }
    window.addEventListener("online", updateConnection);
    window.addEventListener("offline", updateConnection);
    updateConnection();
    if (!form) return;
    const fields = [...form.querySelectorAll("input[name]")].filter(x =>
      !["hidden","submit"].includes(x.type)
    );
    const initial = fields.map(x => x.type === "radio" ? x.checked : x.value);
    let submitting = false;
    form.addEventListener("submit", () => { submitting = true; });
    function changed() {
      return fields.some((x,i) =>
        (x.type === "radio" ? x.checked : x.value) !== initial[i]
      );
    }
    for (const link of nav.querySelectorAll("a[href]")) {
      link.addEventListener("click", (event) => {
        if (!submitting && changed() &&
            !window.confirm("This set has unsaved changes. Switch machines without saving?")) {
          event.preventDefault();
        }
      });
    }
  }
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init, {once:true});
  } else init();
})();
