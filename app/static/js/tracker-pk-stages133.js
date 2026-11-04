(() => {
  "use strict";

  function init() {
    const $=id=>document.getElementById(id);
    if(!$("pkStagePreview"))return;

    const make=()=>({
      start_at:$("pkStageStart").value,
      stages:[
        {
          amount_mg:Number($("pkStageA").value),
          count:Number($("pkStageCountA").value),
          interval_days:Number(
            $("pkStageIntervalA").value
          )
        },
        ...(
          $("pkStageCountB").value
            ?[{
              amount_mg:Number($("pkStageB").value),
              count:Number(
                $("pkStageCountB").value
              ),
              interval_days:Number(
                $("pkStageIntervalB").value
              )
            }]
            :[]
        ),
        ...window.trackerPkExtraStages?.() || []
      ]
    });

    let preview=null;

    async function api(path,body) {
      const headers={
        "Content-Type":"application/json"
      };

      const csrf=window.trackerCsrfToken?.();
      if(csrf)
        headers["X-Tracker-CSRF"]=csrf;

      const response=await fetch(path,{
        method:"POST",
        credentials:"same-origin",
        headers,
        body:JSON.stringify(body)
      });

      if(!response.ok)
        throw Error(
          "HTTP "+response.status+": "+
          (await response.text()).slice(0,160)
        );

      return response.json();
    }

    function invalidate() {
      preview=null;
      $("pkStageReplace").disabled=true;
    }

    [
      "pkStageStart",
      "pkStageA",
      "pkStageCountA",
      "pkStageIntervalA",
      "pkStageB",
      "pkStageCountB",
      "pkStageIntervalB"
    ].forEach(id=>{
      $(id).addEventListener("input",invalidate);
    });

    $("pkStagePreview").onclick=async()=>{
      invalidate();

      try {
        const sid=Number($("scenario").value);
        if(!sid)
          throw Error("Select a scenario");

        const values=make();

        const response=await fetch(
          "/pk/scenarios/"+sid+"/revision",
          {cache:"no-store"}
        );

        if(!response.ok)
          throw Error("Revision unavailable");

        const revision=await response.json();

        const result=await api(
          "/pk/scenarios/"+sid+"/staged-preview",
          values
        );

        const body=$("pkStagePreviewRows");
        body.replaceChildren();

        result.doses.forEach(d=>{
          const tr=document.createElement("tr");

          [
            d.stage,
            d.planned_at,
            d.amount_mg
          ].forEach(value=>{
            const td=document.createElement("td");
            td.textContent=String(value);
            tr.append(td);
          });

          body.append(tr);
        });

        preview={
          sid,
          values:{
            ...values,
            expected_version:revision.version
          }
        };

        $("pkStageReplace").disabled=false;

        $("pkStageStatus").textContent=
          "Previewed "+result.doses.length+
          " doses. Confirmation will replace ALL "+
          "existing hypothetical doses.";
      } catch(error) {
        $("pkStageStatus").textContent=
          error.message;
      }
    };

    $("pkStageReplace").onclick=async()=>{
      if(!preview)return;

      if(
        Number($("scenario").value)!==preview.sid
      ) {
        invalidate();
        return;
      }

      if(!confirm(
        "Replace ALL doses in this hypothetical "+
        "scenario with the staged schedule?"
      ))return;

      const request=preview;
      invalidate();

      try {
        await api(
          "/pk/scenarios/"+
          request.sid+"/staged-replace",
          request.values
        );

        await window.trackerPkReloadScenario();

        $("pkStageStatus").textContent=
          "Staged hypothetical schedule saved.";
      } catch(error) {
        $("pkStageStatus").textContent=
          error.message;
      }
    };

    $("scenario").addEventListener(
      "change",invalidate
    );
  }

  if(document.readyState==="loading")
    document.addEventListener(
      "DOMContentLoaded",init,{once:true}
    );
  else init();
})();
