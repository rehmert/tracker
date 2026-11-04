/*
 * Tracker Batch 52: read-only protocol exposure preview.
 */
(() => {
  "use strict";

  function init() {
    const section = document.getElementById(
      "protocolExposureSection"
    );
    if (!section) return;

    const button = document.getElementById(
      "protocolExposureButton"
    );
    const results = document.getElementById(
      "protocolExposureResults"
    );
    const status = document.getElementById(
      "protocolExposureStatus"
    );

    if (!button || !results || !status) return;

    const protocolId = section.dataset.protocolId;
    let loaded = false;

    function renderGraph(series) {
      const card = document.createElement("section");
      card.className = "protocol-exposure-graph";

      const heading = document.createElement("h3");
      heading.textContent = series.compound;

      const note = document.createElement("p");
      note.className = "note";
      note.textContent =
        series.dose_count + " modeled doses · " +
        series.duration_days + " days · " +
        series.model.level +
        (series.short_window
          ? " · Short-window display for faster PK"
          : "");

      const canvas = document.createElement("canvas");
      canvas.width = 1000;
      canvas.height = 380;
      canvas.className = "pk-chart";
      canvas.setAttribute("role", "img");
      canvas.setAttribute(
        "aria-label",
        "Modeled mg-equivalent exposure for " +
        series.compound
      );

      card.append(heading, note, canvas);

      const ctx = canvas.getContext("2d");
      if (!ctx) {
        const error = document.createElement("p");
        error.textContent = "Canvas is unavailable.";
        card.append(error);
        return card;
      }

      const values = series.values || [];
      const times = series.times || [];

      if (values.length < 2 ||
          values.length !== times.length) {
        const error = document.createElement("p");
        error.textContent = "Insufficient graph samples.";
        card.append(error);
        return card;
      }

      const css = getComputedStyle(document.documentElement);
      const token = (key, fallback) =>
        css.getPropertyValue(key).trim() || fallback;

      const ink = token("--chart-text", "#394a42");
      const grid = token("--chart-grid", "#c9d0c8");
      const color = token("--chart-planned", "#b45309");

      const width = canvas.width;
      const height = canvas.height;
      const left = 84;
      const right = 24;
      const top = 36;
      const bottom = 66;
      const max = Math.max(0.001, ...values);

      ctx.clearRect(0, 0, width, height);

      window.trackerPkAxes.draw({
        ctx,
        width,
        height,
        left,
        right,
        top,
        bottom,
        times,
        maximum: max,
        normalized: false,
        textColor: ink,
        gridColor: grid
      });

      const x = i =>
        left + (width - left - right) *
        i / (values.length - 1);

      const y = value =>
        height - bottom -
        (height - top - bottom) * value / max;

      ctx.beginPath();
      ctx.strokeStyle = color;
      ctx.lineWidth = 2.5;

      values.forEach((value, index) => {
        if (index === 0) ctx.moveTo(x(index), y(value));
        else ctx.lineTo(x(index), y(value));
      });

      ctx.stroke();
      return card;
    }

    function render(data) {
      results.replaceChildren();

      const intro = document.createElement("p");
      intro.className = "note";
      intro.textContent =
        data.status + " protocol · modeled start: " +
        data.start_date +
        (data.assumed_start
          ? " (illustrative: no saved start date)"
          : "") +
        " · " + data.disclaimer;

      results.append(intro);

      (data.graphs || []).forEach(graph => {
        results.append(renderGraph(graph));
      });

      if (!data.graphs?.length) {
        const empty = document.createElement("p");
        empty.textContent =
          "No supported exposure curves for this protocol.";
        results.append(empty);
      }

      if (data.skipped?.length) {
        const heading = document.createElement("h3");
        heading.textContent = "Model limitations";

        const list = document.createElement("ul");

        data.skipped.forEach(item => {
          const row = document.createElement("li");
          row.textContent =
            item.compound + ": " + item.reason;
          list.append(row);
        });

        results.append(heading, list);
      }
    }

    button.addEventListener("click", async () => {
      if (!results.hidden) {
        results.hidden = true;
        button.textContent = "Show model exposure";
        button.setAttribute("aria-expanded", "false");
        return;
      }

      results.hidden = false;
      button.textContent = "Hide model exposure";
      button.setAttribute("aria-expanded", "true");

      if (loaded) return;

      button.disabled = true;
      status.textContent = "Calculating saved protocol exposure…";

      try {
        const response = await fetch(
          "/pk/protocol-exposure/" +
            encodeURIComponent(protocolId),
          {credentials:"same-origin", cache:"no-store"}
        );

        if (!response.ok) {
          throw new Error(
            "Preview failed (HTTP " + response.status + ")"
          );
        }

        render(await response.json());
        loaded = true;
        status.textContent =
          "Exposure preview ready. No records changed.";
      } catch (error) {
        results.hidden = true;
        button.textContent = "Show model exposure";
        button.setAttribute("aria-expanded", "false");
        status.textContent =
          error.message || String(error);
      } finally {
        button.disabled = false;
      }
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener(
      "DOMContentLoaded", init, {once:true}
    );
  } else {
    init();
  }
})();
