/* Release 766: protect unsaved set edits when switching machines. */
(() => {
  "use strict";
  function init() {
    const root = document.getElementById("workout659-root");
    const form = document.getElementById("workout659-log-form");
     const status = document.getElementById("workout766-connection");
    if (!root) return;
    function updateConnection() {
      if (status) status.textContent = navigator.onLine
        ? "Online · only Save Set records a set"
        : "Offline · save a local set draft or use the existing offline queue";
    }
    window.addEventListener("online", updateConnection);
    window.addEventListener("offline", updateConnection);
    updateConnection();
    if (!form || root.dataset.gymHandoffInitialized === "true") return;
    root.dataset.gymHandoffInitialized = "true";
    const fields = [...form.querySelectorAll("input[name], select[name], textarea[name]")].filter(x =>
      !["hidden","submit"].includes(x.type)
    );
    const initial = fields.map(x => ["radio","checkbox"].includes(x.type) ? x.checked : x.value);
    let submitting = false;
    form.addEventListener("submit", () => { submitting = true; });
    function changed() {
      return fields.some((x,i) =>
        (["radio","checkbox"].includes(x.type) ? x.checked : x.value) !== initial[i]
      );
    }
    function allowSwitch() {
      return submitting || !changed() ||
        window.confirm("This set has unsaved changes. Switch machines without saving?");
    }
    // Delegate across the entire Gym Mode: directory, routine, and previous/next.
    root.addEventListener("click", event => {
      const link = event.target.closest("a[href]");
      if (!link) return;
      const href = link.getAttribute("href");
      // Canonical application links are root-relative. Test these without
      // requiring browser navigation or a network origin.
      let machineLink = false;
      if (href.startsWith("/workouts/quick?")) {
        machineLink = new URLSearchParams(href.split("?")[1].split("#")[0]).has("machine");
      } else {
        try {
          const url = new URL(href, window.location.href);
          machineLink = url.origin === window.location.origin &&
            url.pathname === "/workouts/quick" && url.searchParams.has("machine");
        } catch (_) { /* non-navigable relative link */ }
      }
      if (event.defaultPrevented) return;
      if (machineLink && !allowSwitch()) {
        event.preventDefault();
        event.stopImmediatePropagation();
      }
    }, true);
    // Native Go and automatic requestSubmit() both use this same submit guard.
    const picker = root.querySelector("form.workout659-machine-picker");
    const selector = picker?.querySelector('select[name="machine"]');
    const selected = selector?.value;
    picker?.addEventListener("submit", event => {
      if (event.defaultPrevented) return;
      if (!allowSwitch()) {
        event.preventDefault();
        event.stopImmediatePropagation();
        if (selector) selector.value = selected;
      }
    }, true);
  }
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init, {once:true});
  } else init();
})();
