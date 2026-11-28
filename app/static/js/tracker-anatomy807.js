/* One progressive enhancement for existing native site fields.
   No extra form inputs or dose submissions. */
(() => {
  "use strict";
  const ns = "http://www.w3.org/2000/svg";
  const views = ["front", "rear", "left", "right"];
  const labels = {front:"Front · patient right at viewer left", rear:"Rear · patient left at viewer left", left:"Patient left side", right:"Patient right side"};
  const reference = {
    abdomen:"Rectus abdominis lies centrally; the external obliques are lateral. The navel is a central landmark. Intermediate and lateral rectangles are recording areas, not clinical injection instructions.",
    thigh:"The vastus lateralis occupies the lateral thigh; rectus femoris is anterior, vastus medialis medial, and the iliotibial tract lateral. Upper, middle and lower describe relative height between hip and knee.",
    shoulder:"The deltoid has anterior, middle and posterior portions around the shoulder. The acromion and upper humerus are orientation landmarks, not needle-placement targets.",
    gluteal:"The gluteus maximus covers much of the posterior hip and gluteus medius lies superiorly and laterally. Upper/lower and inner/outer are recording subdivisions; the iliac crest and greater trochanter are orientation landmarks."
  };
  function node(name, attributes = {}, text = "") {
    const el = document.createElement(name);
    Object.entries(attributes).forEach(([key,value]) => el.setAttribute(key,value));
    if (text) el.textContent = text;
    return el;
  }
  function vector(name, attributes = {}) {
    const el = document.createElementNS(ns,name);
    Object.entries(attributes).forEach(([key,value]) => el.setAttribute(key,value));
    return el;
  }
  function enhance(select) {
    if (select.dataset.site807Enhanced) return;
    const zones = Array.from(select.options).filter(o => o.dataset.site807).map(o => {
      try { return {code:o.value,label:o.textContent.trim(),...JSON.parse(o.dataset.site807)}; }
      catch { return null; }
    }).filter(Boolean);
    if (!zones.length) return;
    select.dataset.site807Enhanced = "1";
    const parent = select.closest("label") || select;
    const panel = node("details",{class:"site807-picker"});
    const summary = node("summary",{},"Choose recording location on body map");
    panel.append(summary);
    parent.after(panel);
    let initialized = false;
    panel.addEventListener("toggle",() => {
      if (!panel.open || initialized) return;
      initialized = true;
      let view = zones.find(z=>z.code===select.value)?.views[0] || "front";
      const controls = node("div",{class:"site807-controls"});
      const map = vector("svg",{viewBox:"0 0 300 460",class:"site807-map",role:"group","aria-label":"Anatomical recording map"});
      const status = node("p",{class:"site807-status",role:"status","aria-live":"polite"});
      const notes = node("p",{class:"note"},"Schematic recording regions only. Selection does not establish clinical suitability.");
      const refs = node("details",{class:"site807-reference"});
      refs.append(node("summary",{},"Anatomical Reference & Site Identification"));
      const sections = {};
      const regionZoom = {abdomen:["front","90 130 120 100"],thigh:["front","86 245 128 130"],shoulder:["left","100 76 100 95"],gluteal:["rear","88 202 124 72"]};
      Object.entries(reference).forEach(([name,copy])=>{
        const d = node("details");
        d.append(node("summary",{},name.charAt(0).toUpperCase()+name.slice(1)));
        const [angle, bounds] = regionZoom[name];
        const detail = vector("svg",{viewBox:bounds,class:"site807-detail",role:"img","aria-label":name+" schematic magnification"});
        detail.append(vector("use",{href:"/static/anatomy807.svg#"+angle,width:300,height:460}));
        d.append(detail,node("p",{},copy)); refs.append(d); sections[name] = d;
      });
      const orientation=node("p",{},"Anterior = front; posterior = rear; medial = toward midline; lateral = away from midline; superior = above; inferior = below. Left and right always refer to the patient.");
      refs.append(orientation,node("p",{},"The rectangular grid is conceptual and is not a measured three-inch scale. Rotation preferences are recording preferences only; follow the medicine-specific clinical guidance."));
      const links=node("p");
      links.append(node("a",{href:"https://medlineplus.gov/ency/patientinstructions/000430.htm",rel:"noreferrer noopener",target:"_blank"},"MedlinePlus: subcutaneous injections"),document.createTextNode(" · "),node("a",{href:"https://medlineplus.gov/ency/patientinstructions/000935.htm",rel:"noreferrer noopener",target:"_blank"},"MedlinePlus: intramuscular injections"));
      refs.append(links);
      const showRef = node("button",{type:"button"},"Selected region reference");
      showRef.addEventListener("click",()=>{
        const zone = zones.find(z=>z.code===select.value);
        if (!zone) return;
        refs.open = true; sections[zone.region].open = true;
      });
      const buttons = views.map(v=>{
        const b = node("button",{type:"button","aria-pressed":"false"},v[0].toUpperCase()+v.slice(1));
        b.addEventListener("click",()=>{view=v; render();}); controls.append(b); return b;
      });
      const opacityLabel = node("label",{},"Muscle visibility ");
      const opacity = node("input",{type:"range",min:0,max:100,value:100,"aria-label":"Muscle illustration visibility"});
      opacityLabel.append(opacity); controls.append(opacityLabel);
      const zoom=node("button",{type:"button","aria-pressed":"false"},"Zoom selected region");
      let zoomed=false;
      zoom.addEventListener("click",()=>{zoomed=!zoomed; updateZoom();});
      controls.append(zoom);
      const historyLink=node("a",{href:"/health-insights#site-history807",class:"tracker-ui-action"},"Site history");
      const rotationLink=node("a",{href:"/protocols#rotation807",class:"tracker-ui-action"},"Rotation preferences");
      const historyStatus=node("p",{class:"site807-status",role:"status"});
      panel.append(controls,map,status,historyStatus,showRef,historyLink,rotationLink,notes,refs);
      let history=null, requestId=0;
      const form=select.form;
      async function loadHistory() {
        if(!form || location.pathname.startsWith("/secondary/")) return;
        const id=++requestId;
        const params=new URLSearchParams();
        const source=select.dataset.source807 || form.querySelector('[name="vial_id"]')?.value || "";
        const route=form.querySelector('[name="route807"]')?.value || "";
        const item=form.querySelector('[name="calendar_item_id"]')?.value || "";
        if(source) params.set("source",source);
        if(item) params.set("protocol_item",item);
        params.set("route",route);
        try {
          const response=await fetch("/wellness807/site-summary?"+params,{credentials:"same-origin",cache:"no-store"});
          if(!response.ok) throw Error("unavailable");
          const result=await response.json();
          if(id!==requestId) return;
          history=result; update();
        } catch {
          if(id!==requestId) return;
          history=null; historyStatus.textContent="Site history unavailable."; update();
        }
      }
      function updateZoom() {
        const zone=zones.find(z=>z.code===select.value);
        zoom.disabled=!zone || !zone.geometry[view];
        zoom.setAttribute("aria-pressed",String(zoomed && !zoom.disabled));
        if(!zoomed || zoom.disabled) {map.setAttribute("viewBox","0 0 300 460"); return;}
        const g=zone.geometry[view];
        const w=110,h=125;
        map.setAttribute("viewBox",[Math.max(0,Math.min(300-w,g[0]+g[2]/2-w/2)),Math.max(0,Math.min(460-h,g[1]+g[3]/2-h/2)),w,h].join(" "));
      }
      form?.addEventListener("change",e=>{
        if(e.target.matches('[name="vial_id"],[name="route807"]')) loadHistory();
      });
      function choose(code) {
        select.value = code;
        select.dispatchEvent(new Event("change",{bubbles:true}));
      }
      function update() {
        map.querySelectorAll("[data-code]").forEach(el=>{
          const h=history?.sites?.[el.dataset.code];
          el.setAttribute("aria-pressed",String(el.dataset.code===select.value));
          el.classList.toggle("site807-recent",Boolean(h?.recent));
          el.classList.toggle("site807-excluded",Boolean(h?.excluded||h?.active_reactions));
          el.classList.toggle("site807-next",Boolean(h?.next));
          const zone=zones.find(z=>z.code===el.dataset.code);
          const detail=[h?.recent?"recently used":"",h?.excluded?"excluded":"",h?.active_reactions?"reported reaction":"",h?.next?"next configured":"",el.dataset.code===select.value?"selected":""].filter(Boolean).join(", ");
          el.setAttribute("aria-label",zone.label+(detail?", "+detail:""));
          el.querySelector("title").textContent=zone.label+(detail?" · "+detail:"");
        });
        status.textContent = select.selectedOptions[0]?.textContent.trim() || "Not recorded";
        showRef.disabled = !zones.some(z=>z.code===select.value);
        if(history) {
          const h=history.sites?.[select.value];
          const next=history.next_site ? history.sites[history.next_site].label : (history.configured?"No eligible location in configured sequence":"No rotation configured");
          const pieces=h?[h.last?"Last use "+h.last.replace("T"," ").slice(0,16)+" ("+h.elapsed_hours+" h ago)":"No recorded use",h.last_name||"",h.count+" administrations in 90 days",h.active_reactions?h.active_reactions+" unresolved reaction(s)":"No unresolved reaction reported",h.excluded?"Temporarily excluded":h.eligible?"Configured eligible":"Not configured eligible"]:[];
          pieces.push("Next: "+next);
          if(history.truncated) pieces.push("History count limited to latest 5000 records");
          historyStatus.textContent=pieces.filter(Boolean).join(" · ");
        }
        updateZoom();
      }
      function render() {
        buttons.forEach((b,i)=>b.setAttribute("aria-pressed",String(views[i]===view)));
        map.replaceChildren();
        map.setAttribute("aria-label",labels[view]);
        const underlay = vector("use",{href:"/static/anatomy807.svg#"+view,width:300,height:460,opacity:Number(opacity.value)/100});
        map.append(underlay);
        opacity.oninput=()=>underlay.setAttribute("opacity",Number(opacity.value)/100);
        zones.forEach(zone=>{
          const g = zone.geometry[view]; if(!g) return;
          const rect=vector("rect",{x:g[0],y:g[1],width:g[2],height:g[3],rx:3,class:"site807-zone",tabindex:0,role:"button","aria-label":zone.label,"data-code":zone.code,"aria-pressed":"false"});
          const title=vector("title"); title.textContent=zone.label; rect.append(title);
          rect.addEventListener("click",()=>choose(zone.code));
          rect.addEventListener("keydown",e=>{if(e.key==="Enter"||e.key===" "){e.preventDefault();choose(zone.code);}});
          map.append(rect);
        });
        update();
      }
      select.addEventListener("change",update);
      render();
      loadHistory();
    });
  }
  function scan(root) { root.querySelectorAll?.('select[name="site"],select[data-site807-field]').forEach(enhance); }
  document.addEventListener("DOMContentLoaded",()=>scan(document));
  document.addEventListener("htmx:afterSwap",e=>scan(e.target));
})();
