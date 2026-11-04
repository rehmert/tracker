(() => {
  "use strict";

  function init() {
    const $=id=>document.getElementById(id);
    if(!$("pkZoomIn"))return;

    function update() {
      const graph=window.trackerPkLastGraph;

      if(!graph?.rows?.length)return;

      const rows=graph.rows;
      let auc=0;

      for(let i=1;i<rows.length;i++) {
        const hours=(
          new Date(rows[i].at)-
          new Date(rows[i-1].at)
        )/3600000;

        if(hours>0) {
          auc+=hours*(
            rows[i].planned+
            rows[i-1].planned
          )/2;
        }
      }

      const values=rows.map(x=>x.planned);

      $("pkGraphExtraStats").textContent=
        "Visible-window modeled AUC: "+
        auc.toFixed(3)+
        " mg-equivalent·hours · Peak: "+
        Math.max(...values).toFixed(3)+
        " mg-eq · Trough: "+
        Math.min(...values).toFixed(3)+
        " mg-eq";
    }

    document.addEventListener(
      "tracker:pk-graph-updated",update
    );

    function zoom(factor) {
      for(const id of ["back","forward"]) {
        const input=$(id);

        input.value=Math.max(
          1,Math.min(
            365,
            Math.round(
              Number(input.value)*factor
            )
          )
        );
      }

      $("refresh").click();
    }

    $("pkZoomIn").onclick=()=>zoom(.5);
    $("pkZoomOut").onclick=()=>zoom(2);

    $("pkZoomReset").onclick=()=>{
      $("back").value=60;
      $("forward").value=45;
      $("refresh").click();
    };

    $("pkExportAnalysis").onclick=()=>{
      const graph=window.trackerPkLastGraph;

      if(!graph) {
        $("pkGraphExtraStats").textContent=
          "Run the graph first";
        return;
      }

      const record={
        format:"tracker-pk-analysis-v1",
        created_at:new Date().toISOString(),
        scenario_id:$("scenario").value||null,
        compound_id:$("compound").value,
        assumptions:{
          half_life_hours:$("half").value,
          absorption_half_life_hours:$("abs").value
        },
        graph
      };

      const url=URL.createObjectURL(
        new Blob(
          [JSON.stringify(record,null,2)],
          {type:"application/json"}
        )
      );

      const anchor=document.createElement("a");
      anchor.href=url;
      anchor.download="tracker-pk-analysis.json";
      anchor.click();

      setTimeout(
        ()=>URL.revokeObjectURL(url),1000
      );
    };
  }

  if(document.readyState==="loading") {
    document.addEventListener(
      "DOMContentLoaded",init,{once:true}
    );
  } else init();
})();
