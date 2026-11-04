(() => {
  "use strict";

  function init() {
    const scenario=document.getElementById("scenario");
    if(!scenario)return;

    const holder=document.createElement("div");
    holder.className="pk-dose-tools";

    const copy=document.createElement("button");
    copy.type="button";
    copy.textContent="Duplicate scenario";

    const exportButton=document.createElement("button");
    exportButton.type="button";
    exportButton.textContent="Export template JSON";

    const history=document.createElement("button");
    history.type="button";
    history.textContent="View change history";

    const state=document.createElement("p");
    state.setAttribute("role","status");

    holder.append(copy,exportButton,history,state);
    scenario.closest("label").after(holder);

    async function entries() {
      const cid=document.getElementById(
        "compound"
      ).value;

      const response=await fetch(
        "/pk/scenarios?compound_id="+cid,
        {cache:"no-store"}
      );

      if(!response.ok)
        throw Error("Scenario list unavailable");

      return response.json();
    }

    async function selected() {
      const id=Number(scenario.value);

      if(!id)
        throw Error("Select a saved scenario");

      const item=(await entries())
        .find(e=>e.id===id);

      if(!item)
        throw Error("Scenario is no longer present");

      return item;
    }

    copy.onclick=async()=>{
      try {
        const item=await selected();

        if(!confirm(
          "Duplicate "+item.name+
          " and its hypothetical doses?"
        ))return;

        const headers={};
        const csrf=window.trackerCsrfToken?.();

        if(csrf)
          headers["X-Tracker-CSRF"]=csrf;

        const response=await fetch(
          "/pk/scenarios/"+item.id+"/duplicate",
          {method:"POST",headers}
        );

        if(!response.ok)
          throw Error("Duplicate failed");

        const copy=await response.json();

        document.getElementById("compound")
          .dispatchEvent(new Event("change"));

        state.textContent=
          "Created "+copy.name+
          ". Select it in the dropdown.";
      } catch(error) {
        state.textContent=error.message;
      }
    };

    exportButton.onclick=async()=>{
      try {
        const item=await selected();

        const payload={
          format:"tracker-pk-scenario-template-v1",
          name:item.name,
          compound_name:document.getElementById(
            "compound"
          ).selectedOptions[0]?.textContent.split(" — ")[0].trim(),
          half_life_hours:item.half_life_hours,
          absorption_half_life_hours:
            item.absorption_half_life_hours,
          doses:item.doses.map(d=>({
            planned_at:d.planned_at,
            amount_mg:d.amount_mg
          }))
        };

        const url=URL.createObjectURL(
          new Blob(
            [JSON.stringify(payload,null,2)],
            {type:"application/json"}
          )
        );

        const anchor=document.createElement("a");
        anchor.href=url;
        anchor.download="pk-scenario-template.json";
        anchor.click();

        setTimeout(
          ()=>URL.revokeObjectURL(url),1000
        );
      } catch(error) {
        state.textContent=error.message;
      }
    };

    history.onclick=async()=>{
      try {
        const item=await selected();
        const response=await fetch(
          "/pk/scenarios/"+item.id+
          "/change-history"
        );

        if(!response.ok)
          throw Error("History unavailable");

        const data=await response.json();

        state.textContent=data.length
          ?data.map(x=>
            x.action+" · "+x.at
          ).join(" | ")
          :"No tracked batch operations yet";
      } catch(error) {
        state.textContent=error.message;
      }
    };
  }

  if(document.readyState==="loading") {
    document.addEventListener(
      "DOMContentLoaded",init,{once:true}
    );
  } else init();
})();
