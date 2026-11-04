/*
 * Tracker Batch 41: independent PK what-if schedules.
 * Client only previews; it never saves an administration.
 */
(() => {
  "use strict";

  function init() {
    const $ = id => document.getElementById(id);
    const container = $("pkMultiSchedules");
    const add = $("pkMultiAdd");
    const run = $("pkMultiRun");
    const status = $("pkMultiStatus");
    const canvas = $("pkMultiPlot");
    const legend = $("pkMultiLegend");
    const source = $("compound");

    if (!container || !add || !run || !status ||
        !canvas || !legend || !source) return;

    const choices = [...source.options].filter(o => o.value);

    const localDateTime = () => {
      const d = new Date();
      return new Date(
        d.getTime() - d.getTimezoneOffset() * 60000
      ).toISOString().slice(0, 16);
    };

    function inputField(labelText, key, value, type, config = {}) {
      const label = document.createElement("label");
      label.textContent = labelText;

      const input = document.createElement("input");
      input.className = "pk-multi-" + key;
      input.type = type;
      input.value = String(value);

      if (config.min !== undefined) input.min = config.min;
      if (config.max !== undefined) input.max = config.max;
      if (config.step !== undefined) input.step = config.step;

      label.appendChild(input);
      return label;
    }

    function addSchedule() {
      if (container.children.length >= 4) return;

      const box = document.createElement("fieldset");
      box.className = "pk-multi-entry";

      const title = document.createElement("legend");
      title.textContent =
        "Schedule " + (container.children.length + 1);

      const grid = document.createElement("div");
      grid.className = "pk-multi-grid";

      const label = document.createElement("label");
      label.textContent = "Compound";

      const compound = document.createElement("select");
      compound.className = "pk-multi-compound";

      choices.forEach(o => compound.add(o.cloneNode(true)));
      label.appendChild(compound);
      grid.appendChild(label);

      const items = [
        inputField("Timeline start", "start", localDateTime(),
          "datetime-local"),
        inputField("Dose (mg)", "dose", "", "number",
          {min:0.001,max:10000,step:"any"}),
        inputField("Interval (days)", "interval", 7, "number",
          {min:0.125,max:90,step:0.125}),
        inputField("Duration (days)", "duration", 84, "number",
          {min:1,max:365,step:1}),
        inputField("First-dose offset (days)", "offset", 0,
          "number", {min:0,max:90,step:1}),
        inputField("Elimination half-life (hours)", "half", "",
          "number", {min:0.01,max:10000,step:"any"}),
        inputField("Absorption half-life (hours)", "abs", "",
          "number", {min:0.01,max:10000,step:"any"})
      ];

      items.forEach(item => grid.appendChild(item));

      function defaults() {
        const option = compound.selectedOptions[0];
        const illustrative =
          option?.dataset.needsAssumptions === "1";

        box.querySelector(".pk-multi-half").value =
          illustrative ? "" : (option?.dataset.half || "");

        box.querySelector(".pk-multi-abs").value =
          illustrative ? "" : (option?.dataset.abs || "");
      }

      compound.addEventListener("change", defaults);

      const remove = document.createElement("button");
      remove.type = "button";
      remove.className = "pk-multi-remove";
      remove.textContent = "Remove schedule";

      remove.addEventListener("click", () => {
        box.remove();

        [...container.children].forEach((entry, index) => {
          entry.querySelector("legend").textContent =
            "Schedule " + (index + 1);
        });

        add.disabled = false;
      });

      box.append(title, grid, remove);
      container.appendChild(box);
      defaults();

      add.disabled = container.children.length >= 4;
    }

    function required(box, key) {
      const input = box.querySelector(".pk-multi-" + key);

      if (!input || !input.value.trim()) {
        throw new Error("Complete all schedule fields.");
      }

      const value = Number(input.value);

      if (!Number.isFinite(value)) {
        throw new Error("Schedule values must be finite.");
      }

      return value;
    }

    function payload() {
      const entries = [...container.children];

      if (!entries.length) {
        throw new Error("Add at least one schedule.");
      }

      return {
        schedules: entries.map((box, index) => {
          const compound = box.querySelector(".pk-multi-compound");
          const selected = compound.selectedOptions[0];

          return {
            compound_id: Number(compound.value),
            name: "Schedule " + (index + 1) +
              " · " + selected.textContent.split(" — ")[0],
            start_at: box.querySelector(".pk-multi-start").value,
            interval_days: required(box, "interval"),
            duration_days: required(box, "duration"),
            offset_days: required(box, "offset"),
            half_life_hours: required(box, "half"),
            absorption_half_life_hours: required(box, "abs"),
            stages: [{
              week: 1,
              amount_mg: required(box, "dose")
            }]
          };
        })
      };
    }

    function plot(data) {
      const ctx = canvas.getContext("2d");
      if (!ctx) throw new Error("Canvas is unavailable.");

      const times = data.at || [];

      if (times.length < 2) {
        throw new Error("Insufficient chart samples.");
      }

      const width = canvas.width;
      const height = canvas.height;
      const left = 58, right = 18, top = 22, bottom = 48;

      const styles = getComputedStyle(document.documentElement);
      const token = (key, fallback) =>
        styles.getPropertyValue(key).trim() || fallback;

      const colors = [
        token("--chart-actual", "#2563eb"),
        token("--chart-planned", "#b45309"),
        "#16a34a",
        "#a855f7"
      ];

      const x = i =>
        left + (width - left - right) *
          i / (times.length - 1);

      const y = percentage =>
        height - bottom -
        (height - top - bottom) * percentage / 100;

      ctx.clearRect(0, 0, width, height);
      ctx.strokeStyle = token("--chart-grid", "#c9d0c8");
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.moveTo(left, top);
      ctx.lineTo(left, height - bottom);
      ctx.lineTo(width - right, height - bottom);
      ctx.stroke();

      ctx.fillStyle = token("--chart-text", "#394a42");
      ctx.font = "14px sans-serif";
      ctx.fillText("100%", 8, top + 6);
      ctx.fillText("0%", 18, height - bottom);
      ctx.fillText(times[0].slice(0, 10), left, height - 12);
      ctx.fillText(
        times[times.length - 1].slice(0, 10),
        width - 120, height - 12
      );

      legend.replaceChildren();

      data.series.forEach((series, index) => {
        ctx.strokeStyle = colors[index];
        ctx.lineWidth = 2.5;
        ctx.beginPath();

        series.values_percent.forEach((value, i) => {
          if (i) ctx.lineTo(x(i), y(value));
          else ctx.moveTo(x(i), y(value));
        });

        ctx.stroke();

        const item = document.createElement("span");
        item.textContent = "● " + series.name +
          " · " + series.dose_count + " modeled doses";
        item.style.color = colors[index];
        legend.appendChild(item);
      });
    }

    add.addEventListener("click", addSchedule);

    run.addEventListener("click", async () => {
      run.disabled = true;

      try {
        const body = payload();
        status.textContent = "Calculating hypothetical exposure…";

        const headers = {"Content-Type":"application/json"};
        const csrf = window.trackerCsrfToken?.();
        if (csrf) headers["X-Tracker-CSRF"] = csrf;

        const response = await fetch(
          "/pk/what-if/multi-preview",
          {
            method:"POST",
            credentials:"same-origin",
            headers,
            body: JSON.stringify(body)
          }
        );

        if (!response.ok) {
          throw new Error(
            "Simulation error (" + response.status + "): " +
            (await response.text()).slice(0, 300)
          );
        }

        const result = await response.json();
        plot(result);

        status.textContent =
          result.series.length +
          " independent hypothetical schedules compared. Nothing saved.";
      } catch (error) {
        status.textContent = error.message || String(error);
      } finally {
        run.disabled = false;
      }
    });

    if (!choices.length) {
      add.disabled = true;
      run.disabled = true;
      status.textContent = "No supported PK compounds available.";
      return;
    }

    addSchedule();
    addSchedule();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init, {once:true});
  } else {
    init();
  }
})();
