/* Named experiment definitions. No administration writes. */
(() => {
  "use strict";
  function init() {
    const root=document.getElementById("pkExperimentWorkbench");
    if(!root) return;
    const $=id=>document.getElementById(id);
    const id=root.dataset.protocolId;
    const status=$("pkExpLibraryStatus");
    const selected=$("pkExpSaved");
    let rows=[];
    let latest=null;
    let pendingEdits=null;

    async function request(path,method="GET",body=null) {
      const headers={};
      if(body) headers["Content-Type"]="application/json";
      const csrf=window.trackerCsrfToken?.();
      if(csrf && method!=="GET") headers["X-Tracker-CSRF"]=csrf;
      const response=await fetch(path,{
        method,credentials:"same-origin",headers,
        body:body?JSON.stringify(body):undefined,
        cache:"no-store"
      });
      if(!response.ok) throw new Error(
        "Experiment library error: HTTP "+response.status
      );
      return response.json();
    }
    const url="/pk/library/"+encodeURIComponent(id);

    async function refresh() {
      rows=await request(url);
      selected.replaceChildren();
      rows.forEach(row=>{
        selected.add(new Option(
          row.name+" · "+row.saved_at.slice(0,10),
          row.id
        ));
      });
      status.textContent=rows.length+
        " named experiment(s) stored.";
    }

    function controls() {
      return {
        compound_id:Number($("pkExpCompound").value),
        dose_multiplier:Number($("pkExpDose").value)/100,
        interval_multiplier:Number($("pkExpInterval").value)/100,
        start_shift_days:Number($("pkExpShift").value),
        horizon_days:Number($("pkExpHorizon").value),
        skip_dose_index:$("pkExpDoseNumber").value
          ? Number($("pkExpDoseNumber").value)-1:null,
        delay_hours:Number($("pkExpDelay").value),
        lab_analyte:$("pkExpLab").value,
        dose_edits:latest?.settings?.dose_edits || []
      };
    }

    function apply(settings) {
      $("pkExpCompound").value=String(settings.compound_id);
      $("pkExpDose").value=String(settings.dose_multiplier*100);
      $("pkExpInterval").value=String(
        settings.interval_multiplier*100
      );
      $("pkExpShift").value=String(settings.start_shift_days);
      $("pkExpHorizon").value=String(settings.horizon_days);
      $("pkExpDoseNumber").value=settings.skip_dose_index==null
        ? "" : String(settings.skip_dose_index+1);
      $("pkExpDelay").value=String(settings.delay_hours);
      $("pkExpLab").value=settings.lab_analyte||"";
      pendingEdits=settings.dose_edits||[];
      $("pkExpDoseRows").replaceChildren();
      $("pkExpRun").click();
    }

    document.addEventListener(
      "tracker:pk-workbench-ready",()=>{
        if(!pendingEdits) return;
        const edits=pendingEdits;
        pendingEdits=null;
        for(const edit of edits) {
          const row=$("pkExpDoseRows").querySelector(
            'tr[data-index="'+edit.index+'"]'
          );
          if(!row) continue;
          row.querySelector(".pk-edit-action").value=edit.action;
          row.querySelector(".pk-edit-hours").value=String(edit.hours);
          if(edit.amount_mg!=null)
            row.querySelector(".pk-edit-amount").value=
              String(edit.amount_mg);
        }
        if(edits.length) $("pkExpRun").click();
      }
    );

    $("pkExpSave").addEventListener("click",async()=>{
      try {
        const name=$("pkExpName").value.trim();
        if(!name) throw new Error("Enter an experiment name");
        const settings=controls();
        settings.dose_edits=[...$("pkExpDoseRows").querySelectorAll("tr")]
          .map(row=>({
            index:Number(row.dataset.index),
            action:row.querySelector(".pk-edit-action").value,
            hours:Number(row.querySelector(".pk-edit-hours").value),
            amount_mg:Number(row.querySelector(".pk-edit-amount").value)
          })).filter(edit=>edit.action!=="keep");
        latest={settings};
        await request(url,"POST",{name,settings,notes:""});
        await refresh();
        status.textContent="Named experiment saved.";
      } catch(e) {status.textContent=e.message;}
    });

    $("pkExpLoad").addEventListener("click",()=>{
      const row=rows.find(r=>r.id===selected.value);
      if(!row) return;
      latest=row;
      $("pkExpName").value=row.name;
      apply(row.settings);
      status.textContent="Experiment loaded for preview.";
    });

    $("pkExpDelete").addEventListener("click",async()=>{
      if(!selected.value ||
         !window.confirm("Delete selected experiment?")) return;
      try {
        await request(
          url+"/"+encodeURIComponent(selected.value),"DELETE"
        );
        await refresh();
      } catch(e) {status.textContent=e.message;}
    });

    $("pkExpExport").addEventListener("click",()=>{
      const row=rows.find(r=>r.id===selected.value);
      if(!row) return;
      const blob=new Blob(
        [JSON.stringify(row,null,2)],
        {type:"application/json"}
      );
      const link=URL.createObjectURL(blob);
      const a=document.createElement("a");
      a.href=link;
      a.download="tracker-pk-experiment.json";
      a.click();
      setTimeout(()=>URL.revokeObjectURL(link),1000);
    });

    refresh().catch(e=>status.textContent=e.message);
  }
  if(document.readyState==="loading")
    document.addEventListener(
      "DOMContentLoaded",init,{once:true}
    );
  else init();
})();
