/* Compare two to four named experiments without recording doses. */
(() => {
  "use strict";

  function init() {
    const root = document.getElementById(
      "pkExperimentWorkbench"
    );
    if (!root) return;

    const $ = id => document.getElementById(id);
    const list = $("pkExpCompare");
    const out = $("pkExpCompareResults");
    let latest = null;

    $("pkExpCompareRun").addEventListener(
      "click", async () => {
        const ids = [...list.selectedOptions]
          .map(o => o.value);

        if (ids.length < 2 || ids.length > 4) {
          out.textContent = "Select 2–4 experiments";
          return;
        }

        const headers = {
          "Content-Type": "application/json"
        };
        const csrf = window.trackerCsrfToken?.();
        if (csrf) headers["X-Tracker-CSRF"] = csrf;

        try {
          const response = await fetch(
            "/pk/library/" + root.dataset.protocolId +
            "/compare", {
              method: "POST",
              credentials: "same-origin",
              cache: "no-store",
              headers,
              body: JSON.stringify({ids})
            }
          );

          if (!response.ok)
            throw new Error(
              "Comparison HTTP " + response.status
            );

          latest = await response.json();
          out.replaceChildren();

          const table = document.createElement("table");
          const head = document.createElement("tr");

          [
            "Experiment","Peak mg-eq","Trough mg-eq",
            "Future demand mg","Original snapshot"
          ].forEach(label => {
            const th = document.createElement("th");
            th.textContent = label;
            head.append(th);
          });
          table.append(head);

          latest.experiments.forEach(e => {
            const tr = document.createElement("tr");
            [
              e.name,e.peak,e.trough,e.inventory_demand,
              e.snapshot ? "Yes" : "No"
            ].forEach(value => {
              const td = document.createElement("td");
              td.textContent = String(value ?? "—");
              tr.append(td);
            });
            table.append(tr);
          });
          out.append(table);

          const canvas = document.createElement("canvas");
          canvas.width = 900;
          canvas.height = 300;
          canvas.className = "pk-chart";
          canvas.setAttribute(
            "aria-label",
            "Normalized saved experiment comparison"
          );
          out.append(canvas);

          const ctx = canvas.getContext("2d");
          const palette = [
            "#2563eb","#b45309","#059669","#9333ea"
          ];

          ctx.strokeStyle = "#a3a3a3";
          ctx.beginPath();
          ctx.moveTo(60,20);
          ctx.lineTo(60,255);
          ctx.lineTo(880,255);
          ctx.stroke();

          const duration = Math.max(
            ...latest.experiments.map(e =>
              Date.parse(e.times.at(-1)+"Z") -
              Date.parse(e.times[0]+"Z")
            ),1
          );

          latest.experiments.forEach((e,k) => {
            const origin = Date.parse(e.times[0]+"Z");
            const peak = e.peak || 1;
            ctx.beginPath();
            ctx.strokeStyle = palette[k];
            ctx.lineWidth = 2;

            e.values.forEach((value,i) => {
              const x = 60 + 820 * (
                Date.parse(e.times[i]+"Z")-origin
              ) / duration;
              const y = 255-235*value/peak;
              if (i) ctx.lineTo(x,y);
              else ctx.moveTo(x,y);
            });
            ctx.stroke();
          });

          const note = document.createElement("p");
          note.className = "note";
          note.textContent = latest.disclaimer;
          out.append(note);
          $("pkExpCompareExport").disabled = false;
        } catch (err) {
          out.textContent = err.message;
        }
      }
    );

    $("pkExpCompareExport").addEventListener(
      "click", () => {
        if (!latest) return;

        const records = [
          ["Experiment","Peak mg-eq","Trough mg-eq",
           "Demand mg"],
          ...latest.experiments.map(e => [
            e.name,e.peak,e.trough,e.inventory_demand
          ])
        ];

        const csv = "\uFEFF" + records.map(row =>
          row.map(value =>
            '"' + String(value ?? "")
              .replace(/"/g,'""')
              .replace(/^[=+\-@]/,"'$&") + '"'
          ).join(",")
        ).join("\r\n");

        const url = URL.createObjectURL(
          new Blob([csv], {type:"text/csv"})
        );
        const a = document.createElement("a");
        a.href = url;
        a.download = "tracker-experiment-comparison.csv";
        a.click();
        setTimeout(() => URL.revokeObjectURL(url),1000);
      }
    );
  }

  if (document.readyState === "loading")
    document.addEventListener(
      "DOMContentLoaded",init,{once:true}
    );
  else init();
})();
