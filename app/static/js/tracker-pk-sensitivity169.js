(() => {
  'use strict';
  const $=id=>document.getElementById(id);

  function init() {
    if(!$('pkSensitivityRun'))return;

    let latest=null;

    $('pkSensitivityRun').onclick=async()=>{
      const sid=Number($('scenario').value);
      if(!sid)return;

      $('pkSensitivityStatus').textContent=
        'Calculating illustrative sensitivity…';

      try {
        const q=new URLSearchParams({
          days:$('pkSensitivityDays').value
        });

        const response=await fetch(
          '/pk/workspace/'+sid+'/sensitivity?'+q,
          {cache:'no-store'}
        );

        if(!response.ok)
          throw Error(
            'HTTP '+response.status+': '+
            (await response.text()).slice(0,150)
          );

        const result=await response.json();

        if(Number($('scenario').value)!==sid)
          return;

        latest=result;

        const canvas=$('pkSensitivityPlot');
        const ctx=canvas.getContext('2d');
        const w=canvas.width;
        const h=canvas.height;

        ctx.clearRect(0,0,w,h);

        const max=Math.max(
          .001,
          ...result.variants.flatMap(v=>v.points)
        );

        const palette=[
          '#5186af','#bb792b','#38915e'
        ];

        result.variants.forEach((v,j)=>{
          const n=v.points.length;
          ctx.beginPath();
          ctx.strokeStyle=palette[j];
          ctx.lineWidth=2;

          v.points.forEach((y,i)=>{
            const x=45+(w-65)*i/Math.max(1,n-1);
            const yy=h-35-(h-55)*y/max;
            if(i===0)ctx.moveTo(x,yy);
            else ctx.lineTo(x,yy);
          });

          ctx.stroke();
        });

        $('pkSensitivityStatus').textContent=
          result.variants.map(v=>
            v.factor+'× half-life: modeled peak '+
            v.peak.toFixed(3)+' mg-eq'
          ).join(' | ')+
          '. No clinical-effect inference.';

        $('pkSensitivityExport').disabled=false;
      }catch(e) {
        latest=null;
        $('pkSensitivityExport').disabled=true;
        $('pkSensitivityStatus').textContent=e.message;
      }
    };

    $('pkSensitivityExport').onclick=()=>{
      if(!latest)return;
      const url=URL.createObjectURL(
        new Blob(
          [JSON.stringify(latest,null,2)],
          {type:'application/json'}
        )
      );

      const link=document.createElement('a');
      link.href=url;
      link.download='tracker-pk-sensitivity.json';
      link.click();

      setTimeout(
        ()=>URL.revokeObjectURL(url),1000
      );
    };

    $('scenario').addEventListener(
      'change',()=>{
        latest=null;
        $('pkSensitivityExport').disabled=true;
      }
    );
  }

  if(document.readyState==='loading')
    document.addEventListener(
      'DOMContentLoaded',init,{once:true}
    );
  else init();
})();
