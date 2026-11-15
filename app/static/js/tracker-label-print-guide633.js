/* Release 633: print-setup guidance; no printer connection, storage or requests. */
(() => {
  "use strict";
  const layouts = {
    "40x20": {media: "40 × 20 mm", strip: "40 × 20 mm", dots: "320 × 160", count: 1},
    "30x15x2": {media: "30 × 15 mm", strip: "30 × 30 mm", dots: "240 × 240", count: 2},
    "10x20x4": {media: "10 × 20 mm", strip: "40 × 20 mm", dots: "320 × 160", count: 4}
  };
  function init() {
    const layout = document.querySelector('select[name="layout"]');
    const summary = document.getElementById("label633MediaSummary");
    if (!layout || !summary) return;
    function refresh() {
      const config = layouts[layout.value];
      if (!config) {
        summary.textContent = "Select a supported label layout.";
        return;
      }
      summary.textContent = config.count + " sticker" + (config.count === 1 ? "" : "s") +
        " per strip. Sticker: " + config.media + ". Full strip: " +
        config.strip + " (203 DPI: " + config.dots +
        " pixels). Preview zoom does not change exported dimensions.";
    }
    layout.addEventListener("change", refresh);
    refresh();
  }
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init, {once: true});
  } else init();
})();
