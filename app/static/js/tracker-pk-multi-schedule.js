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
    const exportButton = $("pkMultiExportCsv");
    let lastResult = null;
    let revision = 0;

    function invalidate() {
      revision++;
      lastResult = null;
      if (exportButton) exportButton.disabled = true;

      const metrics = $("pkMultiMetrics");
      if (metrics) metrics.replaceChildren();

      const legend = $("pkMultiLegend");
      if (legend) legend.replaceChildren();

      const canvas = $("pkMultiPlot");
      if (canvas) {
        const ctx = canvas.getContext("2d");
        if (ctx) {
          ctx.clearRect(0, 0, canvas.width, canvas.height);
        }
      }
    }

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
      if (key === "name") input.maxLength = 120;

      if (config.min !== undefined) input.min = config.min;
      if (config.max !== undefined) input.max = config.max;
      if (config.step !== undefined) input.step = config.step;

      label.appendChild(input);
      return label;
    }

    function addSchedule(initial = null) {
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
        inputField("Schedule name", "name",
          initial?.name ||
          "Schedule " + (container.children.length + 1),
          "text"),
        inputField("Timeline start", "start", localDateTime(),
          "datetime-local"),
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

      const stages = document.createElement("div");
      stages.className = "pk-multi-stages";

      const heading = document.createElement("h4");
      heading.textContent = "Dose and interval stages";

      const help = document.createElement("p");
      help.className = "note";
      help.textContent =
        "Stages start at week 1, relative to the first " +
        "modeled dose. Leave an interval blank to use " +
        "the schedule default.";

      const table = document.createElement("table");
      const thead = document.createElement("thead");
      const header = document.createElement("tr");

      ["Week", "Dose (mg)", "Interval (days)", "Action"]
        .forEach(text => {
          const th = document.createElement("th");
          th.textContent = text;
          header.appendChild(th);
        });

      thead.appendChild(header);

      const tbody = document.createElement("tbody");
      tbody.className = "pk-multi-stage-rows";
      table.append(thead, tbody);

      function addStage(data = {}) {
        if (tbody.children.length >= 52) return;

        const tr = document.createElement("tr");

        [
          ["week", data.week ?? 1, 1, 52, 1],
          ["amount", data.amount_mg ?? "", 0.001, 10000, "any"],
          ["cadence", data.interval_days ?? "", 0.125, 90, "any"]
        ].forEach(([name, value, min, max, step]) => {
          const td = document.createElement("td");
          const input = document.createElement("input");
          input.type = "number";
          input.className = "pk-multi-stage-" + name;
          input.value = String(value);
          input.min = String(min);
          input.max = String(max);
          input.step = String(step);
          input.setAttribute("aria-label", name);
          td.appendChild(input);
          tr.appendChild(td);
        });

        const td = document.createElement("td");
        const removeStage = document.createElement("button");
        removeStage.type = "button";
        removeStage.textContent = "Remove";

        removeStage.addEventListener("click", () => {
          if (tbody.children.length <= 1) return;
          tr.remove();
          invalidate();
        });

        td.appendChild(removeStage);
        tr.appendChild(td);
        tbody.appendChild(tr);
        invalidate();
      }

      const stageButton = document.createElement("button");
      stageButton.type = "button";
      stageButton.textContent = "Add stage";

      stageButton.addEventListener("click", () => {
        const rows = [...tbody.children];
        const last = rows.length
          ? Number(rows[rows.length - 1]
              .querySelector(".pk-multi-stage-week").value)
          : 0;

        addStage({
          week: Math.min(last + 1, 52),
          amount_mg: ""
        });
      });

      stages.append(heading, help, table, stageButton);

      const duplicate = document.createElement("button");
      duplicate.type = "button";
      duplicate.textContent = "Duplicate schedule";
      duplicate.className = "pk-multi-duplicate";

      duplicate.addEventListener("click", () => {
        if (container.children.length >= 4) return;
        try {
          addSchedule(readSchedule(box));
        } catch (error) {
          status.textContent = error.message || String(error);
        }
      });


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
        invalidate();
      });

      box.append(title, grid, stages, duplicate, remove);
      container.appendChild(box);
      defaults();

      if (initial) {
        compound.value = String(initial.compound_id);

        const values = {
          name: initial.name,
          start: initial.start_at,
          interval: initial.interval_days,
          duration: initial.duration_days,
          offset: initial.offset_days,
          half: initial.half_life_hours,
          abs: initial.absorption_half_life_hours
        };

        Object.entries(values).forEach(([key, value]) => {
          box.querySelector(".pk-multi-" + key).value =
            String(value);
        });

        initial.stages.forEach(stage => addStage(stage));
      } else {
        addStage({week:1, amount_mg:""});
      }

      add.disabled = container.children.length >= 4;
      invalidate();
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

    function readSchedule(box) {
      const compound = box.querySelector(".pk-multi-compound");

      if (!compound.value) {
        throw new Error("Select a compound.");
      }

      const rows = [...box.querySelectorAll(
        ".pk-multi-stage-rows tr"
      )];

      if (!rows.length) {
        throw new Error("At least one stage is required.");
      }

      const stages = rows.map(row => {
        const weekField = row.querySelector(
          ".pk-multi-stage-week"
        );
        const amountField = row.querySelector(
          ".pk-multi-stage-amount"
        );
        const intervalField = row.querySelector(
          ".pk-multi-stage-cadence"
        );

        if (!weekField.value.trim() ||
            !amountField.value.trim()) {
          throw new Error("Stage week and dose are required.");
        }

        const week = Number(weekField.value);
        const amount = Number(amountField.value);
        const interval = intervalField.value.trim()
          ? Number(intervalField.value) : null;

        if (!Number.isInteger(week) || week < 1 || week > 52 ||
            !Number.isFinite(amount) ||
            amount <= 0 || amount > 10000 ||
            (interval !== null &&
             (!Number.isFinite(interval) ||
              interval < 0.125 || interval > 90))) {
          throw new Error("Invalid stage values.");
        }

        return {
          week,
          amount_mg: amount,
          interval_days: interval
        };
      });

      const weeks = stages.map(stage => stage.week);

      if (weeks[0] !== 1 ||
          weeks.some((week, i) =>
            i > 0 && week <= weeks[i - 1])) {
        throw new Error(
          "Stages must start at week 1 and increase uniquely."
        );
      }

      const startAt = box.querySelector(
        ".pk-multi-start"
      ).value;

      if (!startAt) {
        throw new Error("Schedule start is required.");
      }

      const interval = required(box, "interval");
      const duration = required(box, "duration");
      const offset = required(box, "offset");
      const half = required(box, "half");
      const absorption = required(box, "abs");

      if (interval < 0.125 || interval > 90 ||
          !Number.isInteger(duration) ||
          duration < 1 || duration > 365 ||
          !Number.isInteger(offset) ||
          offset < 0 || offset > 90 ||
          offset >= duration ||
          half <= 0 || half > 10000 ||
          absorption <= 0 || absorption > 10000) {
        throw new Error("Schedule parameters are out of range.");
      }

      const name = box.querySelector(
        ".pk-multi-name"
      ).value.trim();

      if (!name || name.length > 120) {
        throw new Error(
          "Schedule names must contain 1–120 characters."
        );
      }

      return {
        compound_id: Number(compound.value),
        name,
        start_at: startAt,
        interval_days: interval,
        duration_days: duration,
        offset_days: offset,
        half_life_hours: half,
        absorption_half_life_hours: absorption,
        stages
      };
    }

    function payload() {
      const entries = [...container.children];

      if (!entries.length) {
        throw new Error("Add at least one schedule.");
      }

      return {
        schedules: entries.map(box => readSchedule(box))
      };
    }

    function renderMetrics(data) {
      const target = $("pkMultiMetrics");
      if (!target) return;

      target.replaceChildren();

      const heading = document.createElement("h3");
      heading.textContent = "Comparison summary";

      const note = document.createElement("p");
      note.className = "note";
      note.textContent =
        "Each schedule is normalized independently. " +
        "Values describe modeled exposure shape, not " +
        "comparable potency or clinical effectiveness.";

      const table = document.createElement("table");
      table.className = "pk-multi-summary-table";

      const header = document.createElement("tr");

      [
        "Schedule",
        "Compound",
        "Modeled doses",
        "Peak time",
        "Mean (% of own peak)"
      ].forEach(label => {
        const th = document.createElement("th");
        th.textContent = label;
        header.appendChild(th);
      });

      const thead = document.createElement("thead");
      thead.appendChild(header);

      const tbody = document.createElement("tbody");

      data.series.forEach(series => {
        const values = series.values_percent;
        const peak = Math.max(...values);
        const index = values.indexOf(peak);

        const mean = values.reduce(
          (sum, value) => sum + value, 0
        ) / Math.max(values.length, 1);

        const row = document.createElement("tr");

        [
          series.name,
          series.compound_name,
          String(series.dose_count),
          data.at[index] || "—",
          Number.isFinite(mean) ? mean.toFixed(1) : "—"
        ].forEach(value => {
          const td = document.createElement("td");
          td.textContent = value;
          row.appendChild(td);
        });

        tbody.appendChild(row);
      });

      table.append(thead, tbody);
      target.append(heading, note, table);
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

    container.addEventListener("input", invalidate);
    container.addEventListener("change", invalidate);

    add.addEventListener("click", () => addSchedule());

    function csvCell(value) {
      return '"' + String(value ?? "")
        .replace(/"/g, '""') + '"';
    }

    function exportCsv() {
      if (!lastResult) return;

      const header = [
        "timestamp",
        ...lastResult.series.map((series, index) =>
          "schedule_" + (index + 1) +
          "_percent_" + series.name
        )
      ];

      const rows = [header];

      lastResult.at.forEach((at, index) => {
        rows.push([
          at,
          ...lastResult.series.map(series =>
            series.values_percent[index]
          )
        ]);
      });

      const csv = "\uFEFF" + rows.map(row =>
        row.map(csvCell).join(",")
      ).join("\r\n");

      const blob = new Blob([csv], {
        type: "text/csv;charset=utf-8"
      });

      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");

      link.href = url;
      link.download = "tracker-pk-multi-comparison.csv";

      document.body.appendChild(link);
      link.click();
      link.remove();

      URL.revokeObjectURL(url);
    }

    if (exportButton) {
      exportButton.disabled = true;
      exportButton.addEventListener("click", exportCsv);
    }


    run.addEventListener("click", async () => {
      run.disabled = true;
      invalidate();

      try {
        const body = payload();
        const requestedRevision = revision;
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

        if (revision !== requestedRevision ||
            JSON.stringify(payload()) !== JSON.stringify(body)) {
          throw new Error(
            "Schedule changed during calculation. Compare again."
          );
        }

        plot(result);
        renderMetrics(result);
        lastResult = result;

        if (exportButton) exportButton.disabled = false;

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
