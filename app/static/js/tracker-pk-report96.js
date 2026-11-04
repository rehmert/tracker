/* Export hypothetical and observed analysis with provenance. */
(() => {
  "use strict";

  function init() {
    const button = document.getElementById(
      "pkExpReportJson"
    );
    if (!button) return;

    let latest = null;

    document.addEventListener(
      "tracker:pk-workbench-ready",
      event => {
        latest = {
          generated_at: new Date().toISOString(),
          model: event.detail.data.model_assumptions,
          model_source: event.detail.data.model_source,
          settings: event.detail.settings,
          analysis: event.detail.data,
          caution:
            "Modeled exposure is not measured serum concentration."
        };
        button.disabled = false;
      }
    );

    button.addEventListener("click", () => {
      if (!latest) return;

      const blob = new Blob(
        [JSON.stringify(latest, null, 2)],
        {type: "application/json"}
      );
      const uri = URL.createObjectURL(blob);
      const anchor = document.createElement("a");

      anchor.href = uri;
      anchor.download = "tracker-pk-analysis.json";
      document.body.append(anchor);
      anchor.click();
      anchor.remove();

      setTimeout(() => URL.revokeObjectURL(uri), 1000);
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener(
      "DOMContentLoaded", init, {once: true}
    );
  } else {
    init();
  }
})();
