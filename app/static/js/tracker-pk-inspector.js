/*
 * Tracker 54–56: chart inspection and analysis.
 * All changes are client-side and read-only.
 */
(() => {
  "use strict";

  const DAY = 86400000;

  function stamp(value) {
    if (typeof value !== "string") return NaN;
    const clean = value.replace(" ", "T");
    return Date.parse(
      /(?:Z|[+-]\d\d:\d\d)$/.test(clean)
        ? clean : clean + "Z"
    );
  }

  function number(value) {
    if (!Number.isFinite(value)) return "—";
    if (value === 0) return "0";
    return Number(value.toPrecision(4)).toString();
  }

  function trapezoid(times, values, start, end) {
    let area = 0;
    let hours = 0;
    for (let i = 1; i < times.length; i++) {
      const a = stamp(times[i - 1]);
      const b = stamp(times[i]);
      if (!(b > a)) continue;

      const l = Math.max(a, start);
      const r = Math.min(b, end);
      if (r <= l) continue;

      const left = values[i - 1] +
        (values[i] - values[i - 1]) * (l - a) / (b - a);
      const right = values[i - 1] +
        (values[i] - values[i - 1]) * (r - a) / (b - a);

      const dt = (r - l) / 3600000;
      area += (left + right) * dt / 2;
      hours += dt;
    }
    return hours > 0 ? area / hours : null;
  }

  function analysis(times, values, doses = []) {
    if (!Array.isArray(times) ||
        !Array.isArray(values) ||
        times.length !== values.length ||
        times.length < 2 ||
        !values.every(Number.isFinite)) return null;

    const peak = Math.max(...values);
    const trough = Math.min(...values);
    const start = stamp(times[0]);
    const end = stamp(times[times.length - 1]);

    const mean = trapezoid(times, values, start, end);
    if (mean === null) return null;

    const result = {
      peak, trough, mean,
      fluctuation: mean > 0
        ? 100 * (peak - trough) / mean
        : null,
      stability: "Not assessable",
      lastIntervalMean: null
    };

    const ordered = doses
      .map(d => ({
        at: stamp(d.at || d.planned_at),
        amount: Number(d.amount_mg)
      }))
      .filter(d => Number.isFinite(d.at) &&
        Number.isFinite(d.amount) && d.amount > 0)
      .sort((a,b) => a.at - b.at);

    // Require five doses for a meaningful check of the
    // last two COMPLETED intervals.
    if (ordered.length < 5) return result;

    const last = ordered.slice(-5);
    const intervals = last.slice(1).map(
      (d,i) => d.at - last[i].at
    );
    const cadence = intervals[0];

    if (cadence <= 0 ||
        intervals.some(d => Math.abs(d-cadence) > 3600000) ||
        last.some(d =>
          Math.abs(d.amount-last[0].amount) >
          Math.max(0.000001, last[0].amount * 0.001)
        )) return result;

    const older = trapezoid(
      times,values,last[2].at,last[3].at
    );
    const newer = trapezoid(
      times,values,last[3].at,last[4].at
    );

    if (older === null || newer === null ||
        older <= 0) return result;

    const change = 100 * (newer-older)/older;
    result.lastIntervalMean = newer;
    result.intervalChangePercent = change;
    result.stability = Math.abs(change) <= 5
      ? "Successive interval means within 5%"
      : "Exposure still changing between intervals";

    return result;
  }

  const instances = new WeakMap();

  function attach(canvas, config) {
    if (!canvas || !config ||
        !config.times || !config.series?.length) return;

    const times = config.times;
    const width = canvas.width;
    const left = config.left ?? 84;
    const right = config.right ?? 24;
    const x0 = left / width;
    const usable = (width-left-right)/width;

    let state = instances.get(canvas);

    if (!state) {
      const wrap = document.createElement("div");
      wrap.className = "pk-inspector-wrap";
      canvas.parentNode.insertBefore(wrap, canvas);
      wrap.appendChild(canvas);

      const cursor = document.createElement("div");
      cursor.className = "pk-inspector-cursor";
      cursor.hidden = true;

      const tip = document.createElement("div");
      tip.className = "pk-inspector-tooltip";
      tip.hidden = true;
      tip.setAttribute("role", "status");

      const markers = document.createElement("div");
      markers.className = "pk-inspector-markers";

      wrap.append(cursor, markers, tip);

      state = {wrap, cursor, tip, markers, config};
      instances.set(canvas, state);

      function move(event) {
        const current = state.config;
        const rect = canvas.getBoundingClientRect();
        if (!rect.width) return;

        const ratio =
          (event.clientX-rect.left)/rect.width;
        const position = Math.max(0,Math.min(1,
          (ratio-state.x0)/state.usable
        ));
        const index = Math.min(
          current.times.length-1,
          Math.round(
            position*(current.times.length-1)
          )
        );

        const location = state.x0+position*state.usable;

        state.cursor.style.left =
          (location*100)+"%";
        state.cursor.hidden = false;

        const details = [
          current.times[index].replace("T"," ")
        ];

        current.series.forEach(line => {
          const value = line.values[index];
          if (Number.isFinite(value)) {
            details.push(
              line.name+": "+number(value)+
              (current.normalized ? "%" : " mg-eq")
            );
          }
        });

        state.tip.textContent = details.join(" · ");
        state.tip.hidden = false;
        state.tip.style.left =
          Math.max(0,Math.min(100,location*100))+"%";
      }

      canvas.addEventListener("pointermove", move);
      canvas.addEventListener("pointerleave", () => {
        state.cursor.hidden = true;
        state.tip.hidden = true;
      });
      canvas.addEventListener("focus", () => {
        const rect = canvas.getBoundingClientRect();
        move({
          clientX:rect.left+rect.width/2
        });
      });
      canvas.addEventListener("blur", () => {
        state.cursor.hidden = true;
        state.tip.hidden = true;
      });
      canvas.tabIndex = 0;
    }

    state.config = config;
    state.x0 = x0;
    state.usable = usable;

    state.markers.replaceChildren();

    const first = stamp(times[0]);
    const last = stamp(times[times.length-1]);

    const markers = (config.doses || [])
      .filter(d => {
        const when = stamp(d.at || d.planned_at);
        return Number.isFinite(when) &&
          when >= first && when <= last;
      });

    // Cap visual markers to avoid overwhelming the graph
    // on high-frequency or very long schedules.
    markers.slice(0,250).forEach(dose => {
      const when = stamp(
        dose.at || dose.planned_at
      );
      const fraction = (when-first)/(last-first);
      if (!Number.isFinite(fraction)) return;

      const node = document.createElement("span");
      node.className = "pk-inspector-dose";
      node.style.left =
        ((x0+fraction*usable)*100)+"%";
      node.title =
        "Modeled dose: "+
        number(Number(dose.amount_mg))+
        " mg · "+(dose.at || dose.planned_at);
      state.markers.appendChild(node);
    });

    state.cursor.hidden = true;
    state.tip.hidden = true;
  }

  function csv(times, series) {
    const quote = value =>
      '"' + String(value ?? "").replace(/"/g,'""') + '"';

    const rows = [
      ["timestamp", ...series.map(s => s.name)]
    ];
    times.forEach((at,i) => {
      rows.push([
        at,...series.map(s => s.values[i] ?? "")
      ]);
    });
    return "\uFEFF"+rows.map(
      row => row.map(quote).join(",")
    ).join("\r\n");
  }

  function download(name, content) {
    const blob = new Blob([content],{
      type:"text/csv;charset=utf-8"
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = name;
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(url),1000);
  }

  window.trackerPkInspector = Object.freeze({
    attach,analysis,csv,download,stamp,number
  });
})();
