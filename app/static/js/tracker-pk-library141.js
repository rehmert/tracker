(() => {
  "use strict";

  function init() {
    const $=id=>document.getElementById(id);
    if(!$("scenario"))return;

    const select=$("scenario");
    const status=$("pkLibraryStatus");
    const key="tracker-pk-favorites-v1";

    function read() {
      try {
        return JSON.parse(
          localStorage.getItem(key)||"{}"
        );
      } catch(_) {
        return {};
      }
    }

    function save(values) {
      try {
        localStorage.setItem(
          key,JSON.stringify(values)
        );
      } catch(_) {}
    }

    function update() {
      const id=select.value;
      const prefs=read();

      $("pkFavorite").textContent=
        prefs[id]?.favorite
          ?"Unfavorite":"Favorite";

      $("pkArchive").textContent=
        prefs[id]?.archived
          ?"Unarchive":"Archive locally";

      $("pkFavorite").disabled=!id;
      $("pkArchive").disabled=!id;
    }

    $("pkFavorite").onclick=()=>{
      const prefs=read();
      const id=select.value;
      if(!id)return;

      prefs[id]={
        ...prefs[id],
        favorite:!prefs[id]?.favorite
      };

      save(prefs);
      update();
    };

    $("pkArchive").onclick=()=>{
      const prefs=read();
      const id=select.value;
      if(!id)return;

      prefs[id]={
        ...prefs[id],
        archived:!prefs[id]?.archived
      };

      save(prefs);
      update();

      status.textContent=
        "Archive is a browser-only preference. "+
        "The scenario remains saved.";
    };

    select.addEventListener("change",update);

    $("pkScenarioSearch").oninput=()=>{
      const query=$("pkScenarioSearch")
        .value.toLowerCase();

      const prefs=read();

      for(const option of select.options) {
        if(!option.value)continue;

        const matches=option.textContent
          .toLowerCase().includes(query);

        option.hidden=!matches||(
          Boolean(prefs[option.value]?.archived)
          &&!$("pkShowArchived").checked
        );
      }
    };

    $("pkShowArchived").onchange=()=>{
      $("pkScenarioSearch").dispatchEvent(
        new Event("input")
      );
    };

    const file=$("pkImportFile");
    let staged=null;

    async function api(path,data) {
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
        body:JSON.stringify(data)
      });

      if(!response.ok)
        throw Error(
          "HTTP "+response.status+": "+
          (await response.text()).slice(0,200)
        );

      return response.json();
    }

    file.onchange=async()=>{
      staged=null;
      $("pkImportConfirm").disabled=true;

      try {
        const raw=JSON.parse(
          await file.files[0].text()
        );

        if(
          !Array.isArray(raw.doses)
          ||raw.doses.length>300
        ) {
          throw Error(
            "Invalid template dose list"
          );
        }

        const selected=$("compound")
          .selectedOptions[0];

        const obj={
          format:raw.format,
          compound_id:Number(raw.compound_id)||null,
          compound_name:String(
            raw.compound_name||raw.compound||""
          ).split(" — ")[0].trim(),
          name:raw.name,
          half_life_hours:raw.half_life_hours,
          absorption_half_life_hours:
            raw.absorption_half_life_hours,
          doses:raw.doses
        };

        const result=await api(
          "/pk/scenarios/import-preview",
          obj
        );

        const currentName=String(
          selected.textContent
        ).split(" — ")[0].trim();

        if(
          currentName.toLowerCase()
          !==result.compound.toLowerCase()
        ) {
          throw Error(
            "Switch to compound "+
            result.compound+
            " before importing"
          );
        }

        staged=obj;
        $("pkImportConfirm").disabled=false;

        status.textContent=
          "Preview "+result.name+": "+
          result.count+" doses, "+
          result.compound+
          ". Confirm to create a new scenario.";
      } catch(error) {
        status.textContent=error.message;
      }
    };

    $("pkImportConfirm").onclick=async()=>{
      if(!staged)return;

      if(!confirm(
        "Import "+staged.name+
        " as a new hypothetical scenario?"
      ))return;

      const data=staged;
      staged=null;
      $("pkImportConfirm").disabled=true;

      try {
        const result=await api(
          "/pk/scenarios/import-confirm",
          data
        );

        await window.trackerPkReloadScenario();

        status.textContent=
          "Imported scenario #"+
          result.id+
          ". Select it from saved scenarios.";
      } catch(error) {
        status.textContent=error.message;
      }
    };

    const observer=new MutationObserver(()=>{
      $("pkScenarioSearch").dispatchEvent(
        new Event("input")
      );
      update();
    });

    observer.observe(select,{
      childList:true
    });

    update();
  }

  if(document.readyState==="loading")
    document.addEventListener(
      "DOMContentLoaded",init,{once:true}
    );
  else init();
})();
