(() => {
  "use strict";

  function init() {
    const $=id=>document.getElementById(id);

    if(!$("plot")||!$("pkZoomIn"))return;

    let original=null;
    let begin=0;
    let end=0;
    let markers=[];

    const canvas=$("plot");

    function resetData(data) {
      if(!data?.rows?.length)return;

      original=data;
      begin=0;
      end=data.rows.length;
      paint();
    }

    function paint() {
      if(!original)return;

      const rows=original.rows.slice(begin,end);
      if(rows.length<2)return;

      const shown={...original,rows};

      window.trackerPkDrawWindow(shown);

      markers=[];

      const first=Date.parse(rows[0].at);
      const last=Date.parse(rows.at(-1).at);

      if(!(last>first))return;

      const ctx=canvas.getContext("2d");
      const width=canvas.width;

      for(const dose of (
        $("pkLayerMarkers")?.checked===false ? [] : (original.planned_schedule||[])
      )) {
        const at=Date.parse(dose.at);

        if(at<first||at>last)continue;

        const x=84+(width-108)*
          (at-first)/(last-first);

        markers.push({x,at:dose.at});

        ctx.beginPath();
        ctx.strokeStyle="#9b5f18";
        ctx.lineWidth=1;
        ctx.moveTo(x,canvas.height-66);
        ctx.lineTo(x,canvas.height-55);
        ctx.stroke();
      }

      $("pkGraphViewport").textContent=
        "Viewing "+
        rows[0].at.slice(0,16).replace("T"," ")+
        " through "+
        rows.at(-1).at.slice(0,16).replace("T"," ")+
        ". "+markers.length+
        " planned-dose markers.";
    }

    function navigate(scale,shift=0) {
      if(!original)return;

      const length=original.rows.length;
      const visible=end-begin;

      const wanted=Math.min(
        length,
        Math.max(2,Math.round(visible*scale))
      );

      const midpoint=(begin+end)/2+
        shift*visible;

      begin=Math.max(
        0,
        Math.min(
          length-wanted,
          Math.round(midpoint-wanted/2)
        )
      );

      end=begin+wanted;
      paint();
    }

    $("pkZoomIn").onclick=()=>navigate(.5);
    $("pkZoomOut").onclick=()=>navigate(2);

    $("pkZoomReset").onclick=()=>{
      if(!original)return;
      begin=0;
      end=original.rows.length;
      paint();
    };

    $("pkPanLeft").onclick=()=>{
      navigate(1,-.3);
    };

    $("pkPanRight").onclick=()=>{
      navigate(1,.3);
    };

    canvas.addEventListener("click",event=>{
      if(!markers.length)return;

      const rect=canvas.getBoundingClientRect();
      const x=(event.clientX-rect.left)*
        canvas.width/rect.width;

      const nearest=markers.reduce((a,b)=>
        Math.abs(b.x-x)<Math.abs(a.x-x)
          ?b:a
      );

      if(Math.abs(nearest.x-x)>12)return;

      window.trackerPkRevealDoseAt?.(
        nearest.at
      );
    });

    document.addEventListener(
      "tracker:pk-graph-updated",
      ()=>{
        resetData(
          window.trackerPkFullGraph
        );
      }
    );
  }

  if(document.readyState==="loading")
    document.addEventListener(
      "DOMContentLoaded",init,{once:true}
    );
  else init();
})();
