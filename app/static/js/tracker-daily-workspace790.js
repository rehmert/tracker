/* Reveal a requested section before native anchor navigation, preserving
   selected date and existing server-generated return URLs. No record storage. */
(() => {
  "use strict";
  function reveal(hash) {
    if (!hash || !hash.startsWith("#")) return;
    let id;
    try { id = decodeURIComponent(hash.slice(1)); } catch (_) { return; }
    const target = document.getElementById(id);
    if (!target || !target.closest(".tracker-daily790, #reg635-catalog, #reg635-schedules, #reg635-history")) return;
    const direct = target.querySelector(":scope > details.tracker-more790");
    if (direct) direct.open = true;
    let section = target.closest("details");
    while (section) {
      section.open = true;
      section = section.parentElement?.closest("details");
    }
    return target;
  }
  function initial() {
    const target = reveal(location.hash);
    if (target) target.scrollIntoView({block:"start"});
  }
  document.addEventListener("click", event => {
    const a = event.target.closest?.("a[href^='#']");
    if (a) reveal(a.getAttribute("href"));
  });
  window.addEventListener("hashchange", initial);
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", initial, {once:true});
  else initial();
})();
