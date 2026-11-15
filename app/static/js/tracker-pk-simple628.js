/* Release 628: read-only PK graph orientation, no schedule or API mutations. */
(() => {
  "use strict";
  function init() {
    const hint = document.getElementById("pk628GraphHint");
    const result = document.getElementById("pkResults");
    if (!hint || !result) return;
    document.addEventListener("tracker:pk-graph-updated", () => {
      const graph = window.trackerPkLastGraph;
      if (!Array.isArray(graph?.rows) || graph.rows.length < 2) {
        hint.textContent = "No exposure points are available for this selection.";
        return;
      }
      const first = new Date(graph.rows[0].at);
      const last = new Date(graph.rows[graph.rows.length - 1].at);
      if (!Number.isFinite(first.getTime()) || !Number.isFinite(last.getTime())) {
        hint.textContent = "Estimated exposure is ready. Use the timeline controls to explore.";
        return;
      }
      const fmt = date => date.toLocaleDateString(undefined, {
        year: "numeric", month: "short", day: "numeric"
      });
      hint.textContent = "Showing " + fmt(first) + " – " + fmt(last) +
        ". Blue excludes future planned doses; orange includes them. These are modeled estimates.";
    });
  }
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init, {once: true});
  } else init();
})();
