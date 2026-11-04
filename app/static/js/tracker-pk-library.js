/*
 * Tracker Batch 71: named experiment library.
 * Save the actual current inputs and dose-row edits.
 * Distinct from actual protocols and administrations.
 */
(() => {
  "use strict";

  function init() {
    const root=document.getElementById(
      "pkExperimentWorkbench"
    );
    if(!root) return;

    const $=id=>document.getElementById(id);
    const status=$("pkExpLibraryStatus");
    const selected=$("pkExpSaved");
    const base="/pk/library/"+
      encodeURIComponent(root.dataset.protocolId);

    let rows=[];
    let pending=null;
    let loading=false;

    async function request(path,method="GET",body) {
      const headers={};
      if(body!==undefined)
        headers["Content-Type"]="application/json";

      const csrf=window.trackerCsrfToken?.();
      if(csrf && method!=="GET")
        headers["X-Tracker-CSRF"]=csrf;

      const response=await fetch(path,{
        method,credentials:"same-origin",
        cache:"no-store",headers,
        body:body===undefined
          ? undefined : JSON.stringify(body)
      });

      if(!response.ok) throw new Error(
        "Experiment library HTTP "+response.status
      );
      return response.json();
    }

    function renderList(preferred) {
      const previous=preferred || selected.value;
      const query=$("pkExpSearch").value.trim().toLowerCase();
      const sort=$("pkExpSort").value;

      const filtered=rows.filter(row=>
        (row.name+" "+(row.notes||""))
          .toLowerCase().includes(query)
      );

      filtered.sort((a,b)=>{
        if(sort==="name")
          return a.name.localeCompare(b.name);
        if(sort==="oldest")
          return a.saved_at.localeCompare(b.saved_at);
        return b.saved_at.localeCompare(a.saved_at);
      });

      selected.replaceChildren();
      filtered.forEach(row=>{
        selected.add(new Option(
          row.name+" · "+row.saved_at.slice(0,10),
          row.id
        ));
      });

      if(filtered.some(row=>row.id===previous))
        selected.value=previous;

      status.textContent=
        filtered.length+" of "+rows.length+
        " saved experiment(s) shown.";
    }

    async function refresh(preferred) {
      rows=await request(base);
      renderList(preferred);
    }

    function doseEdits() {
      return [...$("pkExpDoseRows").querySelectorAll("tr")]
        .map(row=>{
          const action=row.querySelector(
            ".pk-edit-action"
          ).value;
          return {
            index:Number(row.dataset.index),
            action,
            hours:Number(row.querySelector(
              ".pk-edit-hours"
            ).value),
            amount_mg:action==="amount"
              ? Number(row.querySelector(
                  ".pk-edit-amount"
                ).value)
              : null
          };
        })
        .filter(edit=>edit.action!=="keep");
    }

    function currentSettings() {
      return {
        compound_id:Number($("pkExpCompound").value),
        dose_multiplier:Number($("pkExpDose").value)/100,
        interval_multiplier:
          Number($("pkExpInterval").value)/100,
        start_shift_days:Number($("pkExpShift").value),
        horizon_days:Number($("pkExpHorizon").value),
        skip_dose_index:$("pkExpDoseNumber").value.trim()
          ? Number($("pkExpDoseNumber").value)-1
          : null,
        delay_hours:Number($("pkExpDelay").value),
        lab_analyte:$("pkExpLab").value.trim(),
        dose_edits:doseEdits()
      };
    }

    function selectedRow() {
      return rows.find(r=>r.id===selected.value);
    }

    function apply(row) {
      const s=row.settings;
      $("pkExpCompound").value=String(s.compound_id);
      $("pkExpDose").value=String(
        s.dose_multiplier*100
      );
      $("pkExpInterval").value=String(
        s.interval_multiplier*100
      );
      $("pkExpShift").value=String(s.start_shift_days);
      $("pkExpHorizon").value=String(s.horizon_days);
      $("pkExpDoseNumber").value=
        s.skip_dose_index==null
          ? "" : String(s.skip_dose_index+1);
      $("pkExpDelay").value=String(s.delay_hours);
      $("pkExpLab").value=s.lab_analyte || "";
      $("pkExpName").value=row.name;
      $("pkExpNotes").value=row.notes || "";

      pending=s.dose_edits || [];
      $("pkExpDoseRows").replaceChildren();

      const oldVersion=row.source_updated_at;
      const nowVersion=root.dataset.sourceUpdated;

      if(oldVersion && nowVersion &&
          oldVersion!==nowVersion) {
        status.textContent=
          "Warning: source protocol changed since "+
          "this experiment was saved. Review it before use.";
      } else {
        status.textContent=
          "Experiment loaded; recalculating from current "+
          "saved protocol.";
      }

      $("pkExpRun").click();
    }

    document.addEventListener(
      "tracker:pk-workbench-ready",()=>{
        if(pending===null) return;
        const edits=pending;
        pending=null;

        for(const edit of edits){
          const row=$("pkExpDoseRows").querySelector(
            'tr[data-index="'+edit.index+'"]'
          );
          if(!row) continue;

          row.querySelector(
            ".pk-edit-action"
          ).value=edit.action;

          row.querySelector(
            ".pk-edit-hours"
          ).value=String(edit.hours||0);

          if(edit.amount_mg!=null)
            row.querySelector(
              ".pk-edit-amount"
            ).value=String(edit.amount_mg);
        }

        if(edits.length)
          $("pkExpRun").click();
      }
    );

    $("pkExpSave").addEventListener("click",async()=>{
      if(loading) return;
      loading=true;

      try {
        const name=$("pkExpName").value.trim();
        if(!name)
          throw new Error("Enter an experiment name");

        if(pending!==null)
          throw new Error(
            "Finish loading the selected experiment first"
          );

        const saved=await request(
          base,"POST",{
            name,
            notes:$("pkExpNotes").value.trim(),
            settings:currentSettings()
          }
        );

        await refresh(saved.id);
        status.textContent="Experiment saved.";
      } catch(error) {
        status.textContent=error.message;
      } finally {
        loading=false;
      }
    });

    $("pkExpLoad").addEventListener("click",()=>{
      const row=selectedRow();
      if(row) apply(row);
    });

    $("pkExpDelete").addEventListener("click",async()=>{
      const row=selectedRow();
      if(!row) return;
      if(!window.confirm(
        "Delete experiment '"+row.name+"'?"
      )) return;

      try {
        await request(
          base+"/"+encodeURIComponent(row.id),
          "DELETE"
        );
        await refresh();
      } catch(error) {
        status.textContent=error.message;
      }
    });

    $("pkExpExport").addEventListener("click",()=>{
      const row=selectedRow();
      if(!row) return;

      const blob=new Blob(
        [JSON.stringify(row,null,2)],
        {type:"application/json"}
      );
      const url=URL.createObjectURL(blob);
      const link=document.createElement("a");
      link.href=url;
      link.download="tracker-pk-experiment.json";
      document.body.append(link);
      link.click();
      link.remove();
      setTimeout(()=>URL.revokeObjectURL(url),1000);
    });

    $("pkExpSearch").addEventListener(
      "input",()=>renderList()
    );
    $("pkExpSort").addEventListener(
      "change",()=>renderList()
    );

    refresh().catch(
      error=>status.textContent=error.message
    );
  }

  if(document.readyState==="loading")
    document.addEventListener(
      "DOMContentLoaded",init,{once:true}
    );
  else init();
})();
