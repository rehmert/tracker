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
    const exportPng = $("pkMultiExportPng");
    const exportPreset = $("pkMultiExportPreset");
    const importPreset = $("pkMultiImportPreset");
    const presetFile = $("pkMultiPresetFile");
    let lastResult = null;
    let revision = 0;

    function invalidate() {
      revision++;
      lastResult = null;
      if (exportButton) exportButton.disabled = true;
      if (exportPng) exportPng.disabled = true;

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

    // Batch 45: portable, read-only comparison presets.
    const PRESET_FORMAT = "tracker-pk-multi";
    const PRESET_VERSION = 1;
    const MAX_PRESET_BYTES = 131072;

    function validatePreset(raw) {
      if (!raw || typeof raw !== "object" ||
          Array.isArray(raw) ||
          raw.format !== PRESET_FORMAT ||
          raw.version !== PRESET_VERSION) {
        throw new Error("Unsupported comparison preset format.");
      }

      const schedules = raw.schedules;

      if (!Array.isArray(schedules) ||
          schedules.length < 1 || schedules.length > 4) {
        throw new Error("Preset must contain 1–4 schedules.");
      }

      const numbers = (value, min, max, integer = false) =>
        typeof value === "number" &&
        Number.isFinite(value) &&
        value >= min && value <= max &&
        (!integer || Number.isInteger(value));

      const validStart = value => {
        if (typeof value !== "string" ||
            !/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}$/.test(value)) {
          return false;
        }
        const timestamp = Date.parse(value);
        if (!Number.isFinite(timestamp)) return false;
        const date = new Date(timestamp);
        const parts = [
          date.getFullYear(),
          String(date.getMonth() + 1).padStart(2, "0"),
          String(date.getDate()).padStart(2, "0")
        ];
        return parts.join("-") === value.slice(0, 10);
      };

      const validated = schedules.map((schedule, index) => {
        if (!schedule || typeof schedule !== "object" ||
            Array.isArray(schedule)) {
          throw new Error("Invalid schedule " + (index + 1));
        }

        let compound;

        if (schedule.compound_name !== undefined) {
          if (typeof schedule.compound_name !== "string" ||
              !schedule.compound_name.trim()) {
            throw new Error(
              "Invalid compound name in schedule " + (index + 1)
            );
          }

          const requestedName =
            schedule.compound_name.trim().toLowerCase();

          const matches = choices.filter(option =>
            option.textContent.split(" — ")[0]
              .trim().toLowerCase() === requestedName
          );

          if (matches.length !== 1) {
            throw new Error(
              "Compound '" + schedule.compound_name +
              "' is missing or ambiguous in this Tracker. " +
              "Import cancelled without changing schedules."
            );
          }

          compound = matches[0];
        } else {
          // Legacy Batch 45 presets only have local IDs.
          compound = choices.find(option =>
            Number(option.value) === schedule.compound_id
          );
        }

        if (!compound) {
          throw new Error(
            "Compound ID " + schedule.compound_id +
            " is unavailable. Legacy presets require " +
            "matching database compound IDs."
          );
        }

        if (typeof schedule.name !== "string" ||
            !schedule.name.trim() ||
            schedule.name.trim().length > 120 ||
            !validStart(schedule.start_at) ||
            !numbers(schedule.interval_days, 0.125, 90) ||
            !numbers(schedule.duration_days, 1, 365, true) ||
            !numbers(schedule.offset_days, 0, 90, true) ||
            schedule.offset_days >= schedule.duration_days ||
            !numbers(schedule.half_life_hours, 0.000001, 10000) ||
            !numbers(
              schedule.absorption_half_life_hours,
              0.000001, 10000
            )) {
          throw new Error(
            "Invalid parameters in schedule " + (index + 1)
          );
        }

        if (!Array.isArray(schedule.stages) ||
            schedule.stages.length < 1 ||
            schedule.stages.length > 52) {
          throw new Error(
            "Invalid stage count in schedule " + (index + 1)
          );
        }

        let previousWeek = 0;

        const stages = schedule.stages.map((stage, stageIndex) => {
          if (!stage || typeof stage !== "object" ||
              Array.isArray(stage) ||
              !numbers(stage.week, 1, 52, true) ||
              stage.week <= previousWeek ||
              !numbers(stage.amount_mg, 0.000001, 10000) ||
              (stage.interval_days !== null &&
               !numbers(stage.interval_days, 0.125, 90))) {
            throw new Error(
              "Invalid stage " + (stageIndex + 1) +
              " in schedule " + (index + 1)
            );
          }

          previousWeek = stage.week;

          return {
            week: stage.week,
            amount_mg: stage.amount_mg,
            interval_days: stage.interval_days
          };
        });

        if (stages[0].week !== 1) {
          throw new Error("Stages must begin at week 1.");
        }

        return {
          compound_id: Number(compound.value),
          name: schedule.name.trim(),
          start_at: schedule.start_at,
          interval_days: schedule.interval_days,
          duration_days: schedule.duration_days,
          offset_days: schedule.offset_days,
          half_life_hours: schedule.half_life_hours,
          absorption_half_life_hours:
            schedule.absorption_half_life_hours,
          stages
        };
      });

      const starts = validated.map(schedule =>
        Date.parse(schedule.start_at)
      );
      const ends = validated.map((schedule, index) =>
        starts[index] + schedule.duration_days * 86400000
      );

      if (Math.max(...ends) - Math.min(...starts) >
          730 * 86400000) {
        throw new Error(
          "Combined comparison timeline exceeds 730 days."
        );
      }

      return validated;
    }

    function downloadPreset() {
      try {
        const schedules = payload().schedules.map(schedule => {
          const compound = choices.find(option =>
            Number(option.value) === schedule.compound_id
          );

          if (!compound) {
            throw new Error(
              "Cannot export a schedule with an unknown compound."
            );
          }

          return {
            ...schedule,
            compound_name:
              compound.textContent.split(" — ")[0].trim()
          };
        });

        // Validate the exported format before writing the file.
        validatePreset({
          format: PRESET_FORMAT,
          version: PRESET_VERSION,
          schedules
        });

        const preset = {
          format: PRESET_FORMAT,
          version: PRESET_VERSION,
          schedules
        };

        const json = JSON.stringify(preset, null, 2);
        const blob = new Blob([json], {
          type: "application/json"
        });

        const url = URL.createObjectURL(blob);
        const link = document.createElement("a");

        link.href = url;
        link.download = "tracker-pk-comparison-preset.json";

        document.body.appendChild(link);
        link.click();
        link.remove();

        setTimeout(() => URL.revokeObjectURL(url), 1000);

        status.textContent =
          "Comparison setup exported. No records saved.";
      } catch (error) {
        status.textContent = error.message || String(error);
      }
    }

    async function loadPreset(file) {
      if (!file) return;

      if (file.size > MAX_PRESET_BYTES) {
        throw new Error("Preset exceeds the 128 KB limit.");
      }

      let parsed;
      try {
        parsed = JSON.parse(await file.text());
      } catch {
        throw new Error("Preset is not valid JSON.");
      }

      // Validate every schedule before modifying the editor.
      const schedules = validatePreset(parsed);

      if (!window.confirm(
        "Replace the current hypothetical schedules with " +
        schedules.length + " schedules from this preset?"
      )) {
        status.textContent = "Preset import cancelled.";
        return;
      }

      container.replaceChildren();

      schedules.forEach(schedule => addSchedule(schedule));

      add.disabled = container.children.length >= 4;
      invalidate();

      status.textContent =
        schedules.length +
        " hypothetical schedules restored using local " +
        "compound IDs. Select Compare schedules to recalculate.";
    }

    if (exportPreset) {
      exportPreset.addEventListener("click", downloadPreset);
    }

    if (importPreset && presetFile) {
      importPreset.addEventListener("click", () =>
        presetFile.click()
      );

      presetFile.addEventListener("change", async () => {
        try {
          const file = presetFile.files?.[0];
          if (file) await loadPreset(file);
        } catch (error) {
          status.textContent = error.message || String(error);
        } finally {
          presetFile.value = "";
        }
      });
    }

    function exposureStats(times, values) {
      if (!values.length || values.length !== times.length) {
        return null;
      }

      if (!values.every(Number.isFinite)) return null;

      const peak = Math.max(...values);
      const trough = Math.min(...values);
      const peakIndex = values.indexOf(peak);

      let area = 0;
      let totalHours = 0;

      for (let i = 1; i < values.length; i++) {
        // Treat backend naive timestamps as a continuous
        // simulation timeline, independent of browser DST.
        const a = Date.parse(times[i - 1] + "Z");
        const b = Date.parse(times[i] + "Z");
        const hours = (b - a) / 3600000;

        if (!Number.isFinite(hours) || hours <= 0) {
          return null;
        }

        area += (values[i - 1] + values[i]) / 2 * hours;
        totalHours += hours;
      }

      if (totalHours <= 0) return null;

      return {
        peak,
        trough,
        peakIndex,
        mean: area / totalHours,
        range: peak - trough
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
        "comparable potency or clinical effectiveness. " +
        "Time-weighted means span the full shared timeline.";

      const table = document.createElement("table");
      table.className = "pk-multi-summary-table";

      const header = document.createElement("tr");

      [
        "Schedule",
        "Compound",
        "Modeled doses",
        "Peak time",
        "Minimum (%)",
        "Range (percentage points)",
        "Time-weighted mean (%)"
      ].forEach(label => {
        const th = document.createElement("th");
        th.textContent = label;
        header.appendChild(th);
      });

      const thead = document.createElement("thead");
      thead.appendChild(header);

      const tbody = document.createElement("tbody");

      data.series.forEach(series => {
        const stats = exposureStats(
          data.at, series.values_percent
        );

        const row = document.createElement("tr");

        [
          series.name,
          series.compound_name,
          String(series.dose_count),
          stats ? (data.at[stats.peakIndex] || "—") : "—",
          stats ? stats.trough.toFixed(1) : "—",
          stats ? stats.range.toFixed(1) : "—",
          stats ? stats.mean.toFixed(1) : "—"
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

    function exportChartPng() {
      if (!lastResult) return;

      const exportRevision = revision;

      canvas.toBlob(blob => {
        // Do not export a result invalidated while encoding.
        if (revision !== exportRevision || !lastResult) return;

        if (!blob) {
          status.textContent = "Could not create chart image.";
          return;
        }

        const url = URL.createObjectURL(blob);
        const link = document.createElement("a");

        link.href = url;
        link.download = "tracker-pk-multi-comparison.png";

        document.body.appendChild(link);
        link.click();
        link.remove();

        setTimeout(() => URL.revokeObjectURL(url), 1000);
      }, "image/png");
    }

    if (exportPng) {
      exportPng.disabled = true;
      exportPng.addEventListener("click", exportChartPng);
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
        if (exportPng) exportPng.disabled = false;

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
