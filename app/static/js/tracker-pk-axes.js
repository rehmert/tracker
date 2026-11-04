/*
 * Tracker Batch 50: shared pharmacokinetic chart axes.
 *
 * Display-only. Does not alter simulation data or dosing.
 */
(() => {
  "use strict";

  const DAY = 86400000;
  const HOUR = 3600000;

  function timestamp(value) {
    if (typeof value !== "string") return NaN;

    // Interpret naive backend timestamps on a continuous
    // timeline, avoiding browser-local DST discontinuities.
    const normalized = value.replace(" ", "T");
    const iso = /(?:Z|[+-]\d\d:\d\d)$/.test(normalized)
      ? normalized
      : normalized + "Z";

    return Date.parse(iso);
  }

  function compact(value) {
    if (!Number.isFinite(value)) return "—";
    if (value === 0) return "0";

    const magnitude = Math.abs(value);
    const decimals = magnitude >= 100 ? 0 :
      magnitude >= 10 ? 1 :
      magnitude >= 1 ? 2 :
      magnitude >= 0.1 ? 3 : 4;

    return Number(value.toFixed(decimals)).toString();
  }

  function timeScale(hours) {
    if (hours <= 48) return {
      unit: "hours",
      divisor: 1
    };

    if (hours <= 56 * 24) return {
      unit: "days",
      divisor: 24
    };

    return {
      unit: "weeks",
      divisor: 168
    };
  }

  function draw(options) {
    const {
      ctx, width, height,
      left, right, top, bottom,
      times, maximum, normalized,
      textColor, gridColor
    } = options;

    if (!ctx || !Array.isArray(times) ||
        times.length < 2) return;

    const first = timestamp(times[0]);
    const last = timestamp(times[times.length - 1]);

    if (!Number.isFinite(first) ||
        !Number.isFinite(last) ||
        last <= first) return;

    const durationHours = (last - first) / HOUR;
    const scale = timeScale(durationHours);

    const x0 = left;
    const x1 = width - right;
    const y0 = height - bottom;
    const y1 = top;

    const plotWidth = x1 - x0;
    const plotHeight = y0 - y1;

    if (plotWidth <= 0 || plotHeight <= 0) return;

    const max = normalized
      ? 100
      : Math.max(0.000001, maximum);

    ctx.save();
    ctx.font = "12px sans-serif";
    ctx.lineWidth = 1;

    // Five horizontal reference levels.
    for (let step = 0; step <= 4; step++) {
      const fraction = step / 4;
      const y = y0 - fraction * plotHeight;
      const value = fraction * max;

      ctx.strokeStyle = gridColor;
      ctx.globalAlpha = step === 0 ? 0.9 : 0.45;
      ctx.beginPath();
      ctx.moveTo(x0, y);
      ctx.lineTo(x1, y);
      ctx.stroke();
      ctx.globalAlpha = 1;

      ctx.fillStyle = textColor;
      ctx.textAlign = "right";
      ctx.textBaseline = "middle";

      const label = normalized
        ? compact(value) + "%"
        : compact(value);

      ctx.fillText(label, x0 - 9, y);
    }

    // Five elapsed-time reference levels.
    for (let step = 0; step <= 4; step++) {
      const fraction = step / 4;
      const x = x0 + fraction * plotWidth;

      ctx.strokeStyle = gridColor;
      ctx.globalAlpha = step === 0 ? 0.9 : 0.45;
      ctx.beginPath();
      ctx.moveTo(x, y1);
      ctx.lineTo(x, y0);
      ctx.stroke();
      ctx.globalAlpha = 1;

      const elapsed =
        durationHours * fraction / scale.divisor;

      ctx.fillStyle = textColor;
      ctx.textAlign = "center";
      ctx.textBaseline = "top";
      ctx.fillText(
        compact(elapsed),
        x,
        y0 + 8
      );
    }

    ctx.fillStyle = textColor;
    ctx.font = "12px sans-serif";

    ctx.textAlign = "center";
    ctx.textBaseline = "bottom";
    ctx.fillText(
      "Elapsed time (" + scale.unit + ")",
      (x0 + x1) / 2,
      height - 4
    );

    ctx.textAlign = "left";
    ctx.textBaseline = "bottom";
    ctx.fillText(
      normalized
        ? "Normalized exposure (%)"
        : "Modeled exposure (mg-eq)",
      x0,
      Math.max(12, y1 - 5)
    );

    ctx.restore();
  }

  window.trackerPkAxes = Object.freeze({
    draw,
    timeScale,
    compact
  });
})();
