/* Open existing canonical form sections without changing their state or submitting.
 * Capture runs before older page-specific anchor handlers. Native details remain
 * usable without JS. No storage, writes, background requests, or new form endpoints. */
(() => {
  "use strict";
  function reveal(hash) {
    if (!hash || !hash.startsWith("#")) return;
    let id;
    try { id = decodeURIComponent(hash.slice(1)); } catch (_) { return; }
    const target = document.getElementById(id);
    if (!target) return;
    const details = [];
    let node = target.closest("details");
    while (node) { details.push(node); node = node.parentElement?.closest("details"); }
    for (const detail of details.reverse()) detail.open = true;
    return target;
  }
  function initial() {
    // Existing food server-side search must be visible even without a hash.
    if (location.pathname === "/food" && new URLSearchParams(location.search).get("q"))
      reveal("#food-search");
    const target = reveal(location.hash);
    if (target) requestAnimationFrame(() => target.scrollIntoView({block:"start"}));
  }
  document.addEventListener("click", event => {
    const anchor = event.target.closest?.("a[href^='#']");
    if (anchor) reveal(anchor.hash);
  }, true);
  // Required controls in closed advanced sections must be reachable on errors.
  document.addEventListener("invalid", event => {
    let section = event.target.closest?.("details");
    while (section) { section.open = true; section = section.parentElement?.closest("details"); }
  }, true);
  window.addEventListener("hashchange", initial);
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", initial, {once:true});
  else initial();
})();
