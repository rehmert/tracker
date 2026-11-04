/*
 * Batches 57-60: stateless protocol experiment workbench.
 * No local protocol writes or dose logging.
 */
(() => {
  "use strict";

  function init() {
    const host = document.getElementById(
      "pkExperimentWorkbench"
    );
    if (!host) return;

    const $ = id => document.getElementById(id);
    const inspector = window.trackerPkInspector;
    const axes = window.trackerPkAxes;

    const canvas = $("pkExpPlot");
    const resultHost = $("pkExpResults");
    const status = $("pkExpStatus");
    const run = $("pkExpRun");
    const csv = $("pkExpCsv");

    let result = null;

    const number = inspector.number;

    function parameters() {
      return {
        compound_id: Number($("pkExpCompound").value),
        dose_multiplier: Number($("pkExpDose").value)/100,
        interval_multiplier:
          Number($("pkExpInterval").value)/100,
        start_shift_days:Number($("pkExpShift").value),
        horizon_days:Number($("pkExpHorizon").value),
        skip_dose_index:
          $("pkExpDoseNumber").value.trim()
            ? Number($("pkExpDoseNumber").value)-1
            : null,
        delay_hours:Number($("pkExpDelay").value),
        lab_analyte:$("pkExpLab").value.trim()
      };
    }

    function card(label, value) {
      const outer = document.createElement("div");
      const small = document.createElement("small");
      const strong = document.createElement("strong");
      small.textContent = label;
      strong.textContent = value;
      outer.append(small, strong);
      return outer;
    }

    function analysisTable(data) {
      const target = $("pkExpStatistics");
      target.replaceChildren();

      const base = inspector.analysis(
        data.times,
        data.baseline,
        data.baseline_doses
      );
      const modified = inspector.analysis(
        data.times,
        data.modified,
        data.modified_doses
      );

      if (!base || !modified) return;

      const metrics = [
        ["Peak", "peak", "mg-eq"],
        ["Trough", "trough", "mg-eq"],
        ["Time-weighted mean", "mean", "mg-eq"],
        ["Fluctuation", "fluctuation", "% of mean"]
      ];

      metrics.forEach(([label,key,unit]) => {
        target.append(card(
          label,
          number(base[key])+" → "+
          number(modified[key])+" "+unit
        ));
      });

      target.append(card(
        "Saved schedule stability",
        base.stability
      ));
      target.append(card(
        "Experimental stability",
        modified.stability
      ));

      // Simple modeled accumulation descriptor.
      if (data.modified_doses.length >= 4) {
        const doses = data.modified_doses;
        const last = doses[doses.length-1];
        target.append(card(
          "Last modeled administration",
          last.at.replace("T"," ") +
          " · " + number(last.amount_mg)+" mg"
        ));
      }
    }

    function labTable(data) {
      const host = $("pkExpLabs");
      host.replaceChildren();

      const title = document.createElement("h3");
      title.textContent = "Laboratory observations";
      host.append(title);

      const list = $("pkExpLabOptions");
      list.replaceChildren();

      (data.lab_options || []).forEach(name=>{
        const option = document.createElement("option");
        option.value = name;
        list.append(option);
      });

      const labs = data.labs || [];

      if (!labs.length) {
        const note = document.createElement("p");
        note.className = "note";
        note.textContent =
          "No matching dated laboratory results in this " +
          "window. Select an analyte and rerun to inspect it.";
        host.append(note);
        return;
      }

      const table = document.createElement("table");
      const head = document.createElement("tr");

      ["Drawn","Analyte","Measured value","Reference"]
        .forEach(label=>{
          const th = document.createElement("th");
          th.textContent = label;
          head.append(th);
        });

      table.append(head);

      labs.forEach(lab=>{
        const tr = document.createElement("tr");
        const cells = [
          lab.date,
          lab.analyte,
          number(lab.value)+" "+lab.unit,
          (lab.ref_low ?? "—")+" – "+
            (lab.ref_high ?? "—")
        ];
        cells.forEach(value=>{
          const td = document.createElement("td");
          td.textContent = value;
          tr.append(td);
        });
        table.append(tr);
      });

      host.append(table);

      const caution = document.createElement("p");
      caution.className = "note";
      caution.textContent =
        "Laboratory measurements are independent data. " +
        "They are not modeled concentrations and should " +
        "not be interpreted as validation of the curve.";
      host.append(caution);
    }

    function inventorySummary(data) {
      const target = $("pkExpInventory");
      target.replaceChildren();

      const inventory = data.inventory;
      const heading = document.createElement("h3");
      heading.textContent = "Inventory impact (approximate)";
      target.append(heading);

      const summary = document.createElement("div");
      summary.className = "pk-inspector-statistics";

      summary.append(
        card(
          "Recorded remaining mass",
          number(inventory.available_mg)+" mg"
        ),
        card(
          "Saved schedule demand",
          number(inventory.baseline_demand_mg)+" mg"
        ),
        card(
          "Experimental demand",
          number(inventory.modified_demand_mg)+" mg"
        ),
        card(
          "Estimated experiment cost",
          inventory.modified_estimated_cost === null
            ? "Not estimable"
            : "$"+number(
              inventory.modified_estimated_cost
            )
        )
      );

      const note = document.createElement("p");
      note.className = "note";
      note.textContent = inventory.caveat;

      target.append(summary,note);
    }

    function renderGraph(data) {
      const times = data.times;
      const normalized = $("pkExpNormalize").checked;

      const baseMax = Math.max(0,...data.baseline);
      const newMax = Math.max(0,...data.modified);

      const base = normalized
        ? data.baseline.map(v=>
            baseMax>0 ? 100*v/baseMax : 0
          )
        : data.baseline;

      const changed = normalized
        ? data.modified.map(v=>
            newMax>0 ? 100*v/newMax : 0
          )
        : data.modified;

      const max = normalized
        ? 100
        : Math.max(.001,baseMax,newMax);

      const ctx = canvas.getContext("2d");
      if (!ctx) return;

      const width=canvas.width;
      const height=canvas.height;
      const left=84,right=24,top=36,bottom=66;

      const css=getComputedStyle(document.documentElement);
      const token=(name,fallback)=>
        css.getPropertyValue(name).trim() || fallback;

      const blue=token("--chart-actual","#2563eb");
      const orange=token("--chart-planned","#b45309");

      ctx.clearRect(0,0,width,height);

      axes.draw({
        ctx,width,height,left,right,top,bottom,
        times,maximum:max,normalized,
        textColor:token("--chart-text","#394a42"),
        gridColor:token("--chart-grid","#c9d0c8")
      });

      function draw(values,color) {
        ctx.beginPath();
        ctx.lineWidth=2.5;
        ctx.strokeStyle=color;

        values.forEach((value,i)=>{
          const x=left+(width-left-right)*i/
            Math.max(1,values.length-1);
          const y=height-bottom-
            (height-top-bottom)*value/max;
          if (i) ctx.lineTo(x,y);
          else ctx.moveTo(x,y);
        });

        ctx.stroke();
      }

      draw(base,blue);
      draw(changed,orange);

      const showMarkers=$("pkExpMarkers").checked;

      inspector.attach(canvas,{
        times,
        series:[
          {name:"Saved protocol",values:base},
          {name:"Experiment",values:changed}
        ],
        doses:showMarkers
          ? data.modified_doses
          : [],
        normalized,left,right
      });

      // Independent laboratory draw markers aligned
      // to their dates; no shared Y-axis is implied.
      const wrap=canvas.closest(".pk-inspector-wrap");
      if (wrap) {
        wrap.querySelectorAll(".pk-exp-lab-dot")
          .forEach(node=>node.remove());

        const first=inspector.stamp(times[0]);
        const last=inspector.stamp(times.at(-1));

        (data.labs || []).forEach(lab=>{
          const when=inspector.stamp(
            lab.date+"T12:00:00"
          );
          if (when < first || when > last) return;

          const dot=document.createElement("span");
          dot.className="pk-exp-lab-dot";
          dot.style.left=(
            (left/width+
              ((when-first)/(last-first))*
              ((width-left-right)/width))*100
          )+"%";
          dot.title=lab.date+" · "+lab.analyte+
            " · "+number(lab.value)+" "+lab.unit;
          wrap.append(dot);
        });
      }

      $("pkExpLegend").textContent =
        "Blue: saved schedule · Orange: hypothetical " +
        "schedule · Orange bottom ticks: modeled doses" +
        ((data.labs || []).length
          ? " · Purple upper ticks: laboratory draw dates"
          : "") +
        (normalized
          ? " · Each curve normalized independently"
          : " · Modeled mg-equivalent exposure");
    }

    function render(data) {
      result=data;
      resultHost.hidden=false;

      renderGraph(data);
      analysisTable(data);
      inventorySummary(data);
      labTable(data);

      $("pkExpDisclaimer").textContent =
        data.disclaimer+
        (data.assumed_start
          ? " The protocol had no saved start date; " +
            "today was used as the illustrative anchor."
          : "");

      csv.disabled=false;
    }

    async function runExperiment() {
      run.disabled=true;
      csv.disabled=true;
      result=null;
      resultHost.hidden=true;
      status.textContent="Calculating hypothetical exposure…";

      try {
        const headers={"Content-Type":"application/json"};
        const csrf=window.trackerCsrfToken?.();
        if(csrf) headers["X-Tracker-CSRF"]=csrf;

        const response=await fetch(
          "/pk/workbench/"+
          encodeURIComponent(host.dataset.protocolId),
          {
            method:"POST",
            credentials:"same-origin",
            headers,
            body:JSON.stringify(parameters())
          }
        );

        if(!response.ok) {
          throw new Error(
            "Experiment error ("+response.status+"): "+
            (await response.text()).slice(0,250)
          );
        }

        render(await response.json());
        status.textContent=
          "Experiment calculated. Nothing saved.";
      } catch(error) {
        status.textContent=
          error.message || String(error);
      } finally {
        run.disabled=false;
      }
    }

    run.addEventListener("click",runExperiment);

    $("pkExpReset").addEventListener("click",()=>{
      $("pkExpDose").value="100";
      $("pkExpInterval").value="100";
      $("pkExpShift").value="0";
      $("pkExpHorizon").value="84";
      $("pkExpDoseNumber").value="";
      $("pkExpDelay").value="0";
      status.textContent=
        "Inputs restored to saved-schedule defaults. "+
        "Run the experiment to refresh the graph.";
      resultHost.hidden=true;
      result=null;
      csv.disabled=true;
    });

    ["pkExpNormalize","pkExpMarkers"].forEach(id=>{
      $(id).addEventListener("change",()=>{
        if(result) renderGraph(result);

        try {
          localStorage.setItem(
            "tracker-pk-workbench-display",
            JSON.stringify({
              normalized:$("pkExpNormalize").checked,
              markers:$("pkExpMarkers").checked
            })
          );
        } catch (_) {}
      });
    });

    try {
      const preferences=JSON.parse(
        localStorage.getItem(
          "tracker-pk-workbench-display"
        ) || "{}"
      );

      if(typeof preferences.normalized==="boolean")
        $("pkExpNormalize").checked=
          preferences.normalized;

      if(typeof preferences.markers==="boolean")
        $("pkExpMarkers").checked=preferences.markers;
    } catch (_) {}

    csv.addEventListener("click",()=>{
      if(!result) return;

      inspector.download(
        "tracker-protocol-experiment.csv",
        inspector.csv(result.times,[
          {
            name:"Saved (mg-eq)",
            values:result.baseline
          },
          {
            name:"Experiment (mg-eq)",
            values:result.modified
          }
        ])
      );
    });

    $("pkExpPrint").addEventListener(
      "click",()=>window.print()
    );
  }

  if(document.readyState==="loading") {
    document.addEventListener(
      "DOMContentLoaded",init,{once:true}
    );
  } else {
    init();
  }
})();
