/* Release 449: on-screen-only preview zoom for multi-vial label strips.
 * Actual sheet dimensions and PNG/SVG export bytes are never changed.
 */
(() => {
  "use strict";

  const VALUES = new Set(["1", "1.5", "2", "3", "4", "5"]);
  const KEY = "tracker.labelPreviewZoom449";

  function init() {
    const select = document.getElementById("label-preview-zoom449");
    const status = document.getElementById("label-preview-zoom-status449");
    if (!select || !status) return;

    function apply(value) {
      const chosen = VALUES.has(value) ? value : "3";
      select.value = chosen;
      // Applied only to the screen-preview wrapper. @media print removes
      // transforms and restores the original physical millimeter dimensions.
      document.documentElement.style.setProperty(
        "--label-preview-scale", chosen
      );
      status.textContent = "Preview " + (Number(chosen) * 100)
        + "% — screen only; printing and downloads stay actual size.";
      return chosen;
    }

    let saved = null;
    try { saved = sessionStorage.getItem(KEY); }
    catch (_) { /* Browser storage may be blocked. Default stays 300%. */ }
    apply(saved || "3");

    select.addEventListener("change", () => {
      const chosen = apply(select.value);
      try { sessionStorage.setItem(KEY, chosen); }
      catch (_) { /* Zoom remains usable without storage. */ }
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init, {once: true});
  } else {
    init();
  }
})();
