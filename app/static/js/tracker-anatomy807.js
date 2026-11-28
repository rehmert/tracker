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
      Object.entries(reference).forEach(([name,copy])=>{
        const d = node("details"); d.append(node("summary",{},name.charAt(0).toUpperCase()+name.slice(1)),node("p",{},copy)); refs.append(d); sections[name] = d;
      });
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
      panel.append(controls,map,status,showRef,notes,refs);
      function choose(code) {
        select.value = code;
        select.dispatchEvent(new Event("change",{bubbles:true}));
      }
      function update() {
        map.querySelectorAll("[data-code]").forEach(el=>el.setAttribute("aria-pressed",String(el.dataset.code===select.value)));
        status.textContent = select.selectedOptions[0]?.textContent.trim() || "Not recorded";
        showRef.disabled = !zones.some(z=>z.code===select.value);
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
    });
  }
  function scan(root) { root.querySelectorAll?.('select[name="site"]').forEach(enhance); }
  document.addEventListener("DOMContentLoaded",()=>scan(document));
  document.addEventListener("htmx:afterSwap",e=>scan(e.target));
})();
