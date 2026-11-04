/*
 * Tracker 56: compare two read-only saved protocols.
 * Each compound curve is normalized independently.
 */
(() => {
  "use strict";

  function init() {
    const host = document.getElementById(
      "protocolCompareWorkspace"
    );
    if (!host) return;

    const choose = document.getElementById(
      "protocolCompareTarget"
    );
    const button = document.getElementById(
      "protocolCompareButton"
    );
    const csv = document.getElementById(
      "protocolCompareCsv"
    );
    const print = document.getElementById(
      "protocolComparePrint"
    );
    const status = document.getElementById(
      "protocolCompareStatus"
    );
    const output = document.getElementById(
      "protocolCompareResults"
    );

    const engine = window.trackerPkInspector;
    let exportRows = null;

    async function getProtocol(id) {
      const response = await fetch(
        "/pk/protocol-exposure/"+
        encodeURIComponent(id),
        {credentials:"same-origin",cache:"no-store"}
      );
      if (!response.ok) throw new Error(
        "Protocol preview failed: HTTP "+
        response.status
      );
      return response.json();
    }

    // Interpolate by elapsed time, never by raw array
    // indices, since models have different sampling rates.
    function sample(graph, elapsed) {
      const times = graph.times.map(
        value => engine.stamp(value)
      );
      const origin = times[0];
      const target = origin+elapsed;

      if (target < origin ||
          target > times[times.length-1]) return null;

      let lo = 0, hi = times.length-1;
      while (lo+1 < hi) {
        const mid = (lo+hi)>>1;
        if (times[mid] <= target) lo = mid;
        else hi = mid;
      }

      const first = times[lo];
      const last = times[hi];
      if (last === first) return graph.values[lo];

      const a = graph.values[lo];
      const b = graph.values[hi];
      return a+(b-a)*(target-first)/(last-first);
    }

    function graphPair(a,b,labelA,labelB) {
      const section = document.createElement("section");
      section.className = "protocol-exposure-graph";

      const title = document.createElement("h3");
      title.textContent = a.compound;
      section.append(title);

      const note = document.createElement("p");
      note.className = "note";
      note.textContent =
        "Each curve uses its own modeled peak = 100%. "+
        "Values are not comparable drug potency.";
      section.append(note);

      const canvas = document.createElement("canvas");
      canvas.width = 1000;
      canvas.height = 380;
      canvas.className = "pk-chart";
      canvas.setAttribute("role","img");
      canvas.setAttribute(
        "aria-label","Normalized protocol comparison"
      );
      section.append(canvas);

      const ends = [a,b].map(graph =>
        engine.stamp(graph.times.at(-1))-
        engine.stamp(graph.times[0])
      );
      const duration = Math.max(...ends);
      if (!(duration > 0)) return section;

      // Common elapsed-time sampling. Do not extrapolate
      // curves beyond each protocol's modeled horizon.
      const steps = 240;
      const times = [];
      const valuesA = [];
      const valuesB = [];
      const origin = engine.stamp(a.times[0]);

      const maxA = Math.max(0,...a.values);
      const maxB = Math.max(0,...b.values);

      for (let i=0;i<=steps;i++) {
        const elapsed = duration*i/steps;
        times.push(
          new Date(origin+elapsed).toISOString()
        );

        const x = sample(a,elapsed);
        const y = sample(b,elapsed);

        valuesA.push(
          x === null || maxA<=0 ? null : 100*x/maxA
        );
        valuesB.push(
          y === null || maxB<=0 ? null : 100*y/maxB
        );
      }

      const ctx = canvas.getContext("2d");
      if (!ctx) return section;

      const width=canvas.width,height=canvas.height;
      const left=76,right=24,top=36,bottom=66;
      const css=getComputedStyle(document.documentElement);
      const token=(key,fallback) =>
        css.getPropertyValue(key).trim()||fallback;
      const ink=token("--chart-text","#394a42");
      const grid=token("--chart-grid","#c9d0c8");

      window.trackerPkAxes.draw({
        ctx,width,height,left,right,top,bottom,
        times,maximum:100,normalized:true,
        textColor:ink,gridColor:grid
      });

      function line(values,color) {
        ctx.strokeStyle = color;
        ctx.lineWidth = 2.5;
        ctx.beginPath();
        let open = false;
        values.forEach((value,i)=>{
          if (value === null) {
            open = false;
            return;
          }
          const x=left+(width-left-right)*i/steps;
          const y=height-bottom-
            (height-top-bottom)*value/100;
          if (open) ctx.lineTo(x,y);
          else ctx.moveTo(x,y);
          open = true;
        });
        ctx.stroke();
      }

      line(valuesA,token("--chart-actual","#2563eb"));
      line(valuesB,token("--chart-planned","#b45309"));

      const legend = document.createElement("p");
      legend.className = "note";
      legend.textContent =
        "Blue: "+labelA+
        " · Orange: "+labelB;
      section.append(legend);

      engine.attach(canvas,{
        times,
        series:[
          {name:labelA,values:valuesA},
          {name:labelB,values:valuesB}
        ],
        left,right,normalized:true
      });

      return {
        element:section,
        times,
        valuesA,
        valuesB,
        compound:a.compound
      };
    }

    button.addEventListener("click",async()=>{
      if (!choose.value) {
        status.textContent = "Choose another protocol.";
        return;
      }
      button.disabled = true;
      csv.disabled = true;
      exportRows = null;
      output.replaceChildren();
      status.textContent = "Comparing saved protocols…";

      try {
        const [a,b] = await Promise.all([
          getProtocol(host.dataset.protocolId),
          getProtocol(choose.value)
        ]);

        const comparison = b.graphs || [];
        const pairs = [];
        const names = [];

        (a.graphs || []).forEach(first => {
          const second = comparison.find(
            other => other.compound.toLowerCase() ===
              first.compound.toLowerCase()
          );
          if (second) {
            pairs.push(
              graphPair(first,second,a.protocol,b.protocol)
            );
          } else {
            names.push(first.compound);
          }
        });

        if (!pairs.length) {
          status.textContent =
            "These protocols have no matching "+
            "PK-supported compounds.";
          return;
        }

        const csvParts = [];
        pairs.forEach(pair=>{
          output.append(pair.element);
          csvParts.push(
            engine.csv(pair.times,[
              {
                name:pair.compound+" · "+a.protocol+" (%)",
                values:pair.valuesA
              },
              {
                name:pair.compound+" · "+b.protocol+" (%)",
                values:pair.valuesB
              }
            ])
          );
        });

        exportRows = csvParts.join("\r\n\r\n");
        csv.disabled = false;

        status.textContent =
          pairs.length+" matching compound(s) compared."+
          (names.length
            ? " Unmatched in first protocol: "+
              names.join(", ")+"."
            : "")+
          " No records changed.";
      } catch(error) {
        status.textContent =
          error.message || String(error);
      } finally {
        button.disabled = false;
      }
    });

    csv.addEventListener("click",()=>{
      if (exportRows) engine.download(
        "tracker-protocol-comparison.csv",
        exportRows
      );
    });

    print.addEventListener("click",()=>window.print());
  }

  if (document.readyState === "loading") {
    document.addEventListener(
      "DOMContentLoaded",init,{once:true}
    );
  } else {
    init();
  }
})();
