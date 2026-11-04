/*
 * Tracker Batch 69: separately scaled observed lab trends.
 * Not a PK concentration graph; no writes.
 */
(() => {
  "use strict";

  function stamp(day) {
    return Date.parse(day+"T12:00:00Z");
  }

  function render(data, target) {
    const observations=(data.labs || []).filter(
      row => Number.isFinite(Number(row.value)) &&
        /^\d{4}-\d{2}-\d{2}$/.test(row.date)
    );

    if (!observations.length) return;

    const groups=new Map();
    observations.forEach(row=>{
      const key=row.analyte.toLowerCase()+"\u0000"+row.unit;
      if(!groups.has(key)) groups.set(key,[]);
      groups.get(key).push(row);
    });

    const section=document.createElement("section");
    section.className="pk-lab-trends";

    const title=document.createElement("h3");
    title.textContent="Observed laboratory trends";
    section.append(title);

    const caveat=document.createElement("p");
    caveat.className="note";
    caveat.textContent=
      "Each analyte and recorded unit has its own scale. "+
      "Points represent actual laboratory observations, "+
      "not predicted drug concentrations. "+
      "No PK curve is fitted to laboratory results.";
    section.append(caveat);

    [...groups.values()].slice(0,9).forEach(items=>{
      items.sort((a,b)=>a.date.localeCompare(b.date));

      const card=document.createElement("section");
      card.className="pk-lab-trend-card";

      const label=document.createElement("h4");
      label.textContent=
        items[0].analyte+" ("+items[0].unit+")";
      card.append(label);

      const canvas=document.createElement("canvas");
      canvas.width=920;
      canvas.height=230;
      canvas.className="pk-chart";
      canvas.setAttribute("role","img");
      canvas.setAttribute(
        "aria-label",
        items[0].analyte+" laboratory trend in "+
        items[0].unit
      );

      card.append(canvas);
      section.append(card);

      const ctx=canvas.getContext("2d");
      if(!ctx) return;

      const left=76,right=25,top=25,bottom=48;
      const x0=left,x1=canvas.width-right;
      const y0=canvas.height-bottom,y1=top;

      const values=items.map(p=>Number(p.value));
      let min=Math.min(...values);
      let max=Math.max(...values);

      const pad=Math.max(
        0.001,(max-min)*0.15,
        Math.abs(max)*0.03
      );
      min-=pad;max+=pad;

      const dates=items.map(p=>stamp(p.date));
      let first=dates[0],last=dates.at(-1);

      if(first===last) {
        first-=43200000;
        last+=43200000;
      }

      const X=t=>x0+(x1-x0)*(t-first)/(last-first);
      const Y=v=>y0-(y0-y1)*(v-min)/(max-min);

      const styles=getComputedStyle(document.documentElement);
      const token=(key,fallback)=>
        styles.getPropertyValue(key).trim()||fallback;
      const ink=token("--chart-text","#394a42");
      const grid=token("--chart-grid","#c9d0c8");
      const line=token("--chart-actual","#2563eb");

      ctx.font="12px sans-serif";
      ctx.fillStyle=ink;
      ctx.strokeStyle=grid;
      ctx.lineWidth=1;

      for(let tick=0;tick<=4;tick++){
        const fraction=tick/4;
        const y=y0-fraction*(y0-y1);
        ctx.beginPath();
        ctx.moveTo(x0,y);
        ctx.lineTo(x1,y);
        ctx.stroke();
        ctx.fillStyle=ink;
        ctx.textAlign="right";
        ctx.fillText(
          Number((min+fraction*(max-min)).toPrecision(4)),
          x0-10,y+4
        );
      }

      ctx.strokeStyle=line;
      ctx.lineWidth=2;
      ctx.beginPath();

      items.forEach((item,index)=>{
        const x=X(dates[index]);
        const y=Y(Number(item.value));
        if(index) ctx.lineTo(x,y);
        else ctx.moveTo(x,y);
      });
      ctx.stroke();

      items.forEach((item,index)=>{
        const x=X(dates[index]);
        const y=Y(Number(item.value));

        ctx.beginPath();
        ctx.arc(x,y,4,0,Math.PI*2);
        ctx.fillStyle=line;
        ctx.fill();
      });

      ctx.fillStyle=ink;
      ctx.textAlign="left";
      ctx.fillText(items[0].date,x0,y0+25);
      ctx.textAlign="right";
      ctx.fillText(
        items.at(-1).date,x1,y0+25
      );

      const detail=document.createElement("p");
      detail.className="note";
      detail.textContent=
        items.length+" measured point(s) · "+
        "first: "+items[0].date+" · latest: "+
        items.at(-1).date;
      card.append(detail);
    });

    target.append(section);
  }

  window.trackerPkLabTrends=Object.freeze({render});
})();
