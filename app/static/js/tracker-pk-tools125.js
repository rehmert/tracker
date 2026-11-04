/* PK scenario tools: hypothetical doses only. */
(() => {
  "use strict";

  function init() {
    const $=id=>document.getElementById(id);
    if(!$("plannedRows")) return;

    let sid=null;
    let lastUndo=null;
    let preview=null;
    let busy=false;
    const selected=new Set();

    async function api(path,method="GET",body) {
      const headers={};

      if(body)
        headers["Content-Type"]="application/json";

      if(method!=="GET") {
        const csrf=window.trackerCsrfToken?.();
        if(csrf) headers["X-Tracker-CSRF"]=csrf;
      }

      const response=await fetch("/pk"+path,{
        method,
        headers,
        credentials:"same-origin",
        cache:"no-store",
        body:body?JSON.stringify(body):undefined
      });

      if(!response.ok) {
        throw new Error(
          "HTTP "+response.status+": "+
          (await response.text()).slice(0,180)
        );
      }

      return response.json();
    }

    const status=message=>{
      $("pkBatchStatus").textContent=message;
    };

    function count() {
      $("pkSelectedCount").textContent=
        selected.size+" selected";

      $("pkDeleteSelected").disabled=
        !selected.size||busy;
    }

    async function reload() {
      $("scenario").dispatchEvent(
        new Event("change")
      );
    }

    function filter() {
      const mode=$("pkDoseFilter").value;
      window.trackerPkDoseSort=$("pkDoseSort").value;

      window.trackerPkDoseFilter=d=>
        mode==="all"||
        (mode==="future"
          ?new Date(d.planned_at)>=new Date()
          :new Date(d.planned_at)<new Date());

      $("pkPlannedPageSize").dispatchEvent(
        new Event("change")
      );
    }

    $("pkDoseFilter").onchange=filter;
    $("pkDoseSort").onchange=filter;

    document.addEventListener(
      "tracker:pk-dose-rows",event=>{
        if(sid!==event.detail.scenarioId) {
          sid=event.detail.scenarioId;
          selected.clear();
          lastUndo=null;
          $("pkUndoDelete").hidden=true;
        }

        const doses=event.detail.doses;
        const known=new Set(doses.map(d=>d.id));

        for(const id of selected) {
          if(!known.has(id))selected.delete(id);
        }

        for(const row of $("plannedRows")
          .querySelectorAll("tr[data-dose-id]")) {

          const id=Number(row.dataset.doseId);
          const dose=doses.find(d=>d.id===id);

          if(!dose)continue;

          const cell=document.createElement("td");
          const box=document.createElement("input");

          box.type="checkbox";
          box.checked=selected.has(id);
          box.setAttribute(
            "aria-label","Select dose "+id
          );

          box.onchange=()=>{
            if(box.checked)selected.add(id);
            else selected.delete(id);
            count();
          };

          cell.append(box);
          row.prepend(cell);

          const edit=[...row.querySelectorAll("button")]
            .find(b=>b.textContent==="Edit");

          if(!edit)continue;

          edit.onclick=()=>{
            const time=document.createElement("input");
            time.type="datetime-local";
            time.value=dose.planned_at.slice(0,16);

            const amount=document.createElement("input");
            amount.type="number";
            amount.min=".001";
            amount.step="any";
            amount.value=String(dose.amount_mg);

            row.children[1].replaceChildren(time);
            row.children[2].replaceChildren(amount);

            const save=document.createElement("button");
            save.type="button";
            save.textContent="Save";

            const cancel=document.createElement("button");
            cancel.type="button";
            cancel.textContent="Cancel";
            cancel.onclick=reload;

            save.onclick=async()=>{
              if(busy)return;

              if(
                !time.value||
                !(Number(amount.value)>0)
              ) {
                status("Enter valid date and amount");
                return;
              }

              busy=true;
              save.disabled=true;

              try {
                await api(
                  "/scenarios/"+sid+"/doses/"+id,
                  "PUT",{
                    planned_at:time.value,
                    amount_mg:Number(amount.value)
                  }
                );
                await reload();
                status("Planned dose updated");
              } catch(error) {
                status(error.message);
              } finally {
                busy=false;
                save.disabled=false;
              }
            };

            row.lastElementChild.replaceChildren(
              save,cancel
            );
            time.focus();
          };
        }

        count();
      }
    );

    $("pkDeleteSelected").onclick=async()=>{
      if(!sid||!selected.size||busy)return;

      const ids=[...selected];

      if(!confirm(
        "Delete "+ids.length+
        " hypothetical planned doses?"
      ))return;

      busy=true;
      count();

      try {
        const version=await api(
          "/scenarios/"+sid+"/dose-state"
        );

        const result=await api(
          "/scenarios/"+sid+"/doses/delete-batch",
          "POST",{
            ids,
            expected_version:version.version
          }
        );

        lastUndo={
          sid,
          audit_id:result.audit_id,
          expected_version:result.version
        };

        $("pkUndoDelete").hidden=false;
        selected.clear();
        await reload();

        status(
          "Deleted "+result.deleted+
          " hypothetical doses. Undo is available "+
          "until the scenario changes."
        );
      } catch(error) {
        status(error.message);
      } finally {
        busy=false;
        count();
      }
    };

    $("pkUndoDelete").onclick=async()=>{
      if(
        !lastUndo||busy||
        lastUndo.sid!==sid
      )return;

      busy=true;

      try {
        const result=await api(
          "/scenarios/"+sid+"/doses/undo-delete",
          "POST",lastUndo
        );

        lastUndo=null;
        $("pkUndoDelete").hidden=true;

        await reload();
        status("Restored "+result.restored+" doses");
      } catch(error) {
        status(error.message);
      } finally {
        busy=false;
      }
    };

    const parameters=()=>({
      start_at:$("pkBatchStart").value,
      amount_mg:Number($("pkBatchAmount").value),
      interval_days:Number($("pkBatchInterval").value),
      count:Number($("pkBatchCount").value)
    });

    for(const id of [
      "pkBatchStart","pkBatchAmount",
      "pkBatchInterval","pkBatchCount"
    ]) {
      $(id).oninput=()=>{
        preview=null;
        $("pkBatchSave").disabled=true;
      };
    }

    $("pkBatchPreview").onclick=async()=>{
      preview=null;
      $("pkBatchSave").disabled=true;
      $("pkBatchPreviewRows").replaceChildren();

      if(!sid) {
        status("Select a saved scenario first");
        return;
      }

      try {
        const value=parameters();
        const result=await api(
          "/scenarios/"+sid+
          "/doses/generate-preview",
          "POST",value
        );

        preview={sid,value};

        for(const dose of result.doses) {
          const row=document.createElement("tr");

          for(const value of [
            dose.planned_at,dose.amount_mg
          ]) {
            const cell=document.createElement("td");
            cell.textContent=String(value);
            row.append(cell);
          }

          $("pkBatchPreviewRows").append(row);
        }

        status(
          "Preview: "+result.doses.length+
          " hypothetical doses; not saved"
        );
        $("pkBatchSave").disabled=false;
      } catch(error) {
        status(error.message);
      }
    };

    $("pkBatchSave").onclick=async()=>{
      if(
        !preview||preview.sid!==sid||busy
      )return;

      busy=true;
      $("pkBatchSave").disabled=true;

      try {
        const result=await api(
          "/scenarios/"+sid+"/doses/create-batch",
          "POST",preview.value
        );

        preview=null;
        await reload();

        status(
          "Created "+result.created+
          " hypothetical doses"
        );
      } catch(error) {
        status(error.message);
      } finally {
        busy=false;
      }
    };

    count();
  }

  if(document.readyState==="loading") {
    document.addEventListener(
      "DOMContentLoaded",init,{once:true}
    );
  } else init();
})();
