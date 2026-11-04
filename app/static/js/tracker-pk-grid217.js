(() => {
  'use strict';

  const $=id=>document.getElementById(id);

  function init(){
    if(!$('pkGrid217Run'))return;

    let sequence=0;

    $('pkGrid217Run').onclick=async()=>{
      const sid=Number($('scenario').value);
      const seq=++sequence;

      if(!sid){
        $('pkGrid217Status').textContent=
          'Select a saved scenario';
        return;
      }

      try{
        const response=await fetch(
          '/pk/workspace/'+sid+
          '/sensitivity-grid?days='+
          encodeURIComponent(
            $('pkSensitivityDays').value
          ),
          {cache:'no-store'}
        );

        if(!response.ok)
          throw Error('HTTP '+response.status);

        const data=await response.json();

        if(
          seq!==sequence||
          sid!==Number($('scenario').value)
        )return;

        const c=$('pkGrid217Plot');
        const ctx=c.getContext('2d');
        const w=c.width;
        const h=c.height;

        const max=Math.max(
          .001,...data.upper
        );

        ctx.clearRect(0,0,w,h);

        const x=i=>
          40+(w-60)*i/
          Math.max(1,data.times.length-1);

        const y=v=>
          h-22-(h-40)*v/max;

        ctx.fillStyle='rgba(45,135,185,.18)';
        ctx.beginPath();

        data.upper.forEach((v,i)=>
          i
            ?ctx.lineTo(x(i),y(v))
            :ctx.moveTo(x(i),y(v))
        );

        for(let i=data.lower.length-1;i>=0;i--)
          ctx.lineTo(x(i),y(data.lower[i]));

        ctx.closePath();
        ctx.fill();

        const baseline=data.variants.find(
          v=>v.elimination_factor===1&&
            v.absorption_factor===1
        );

        ctx.strokeStyle='#297cb1';
        ctx.lineWidth=2.5;
        ctx.beginPath();

        baseline.points.forEach((v,i)=>
          i
            ?ctx.lineTo(x(i),y(v))
            :ctx.moveTo(x(i),y(v))
        );

        ctx.stroke();

        $('pkGrid217Status').textContent=
          '9-model assumption-sensitivity envelope, '+
          data.sample_interval_hours.toFixed(2)+
          '-hour samples. Not a confidence interval.';

      }catch(error){
        if(seq===sequence)
          $('pkGrid217Status').textContent=
            error.message;
      }
    };

    $('scenario').addEventListener('change',()=>{
      sequence++;
      $('pkGrid217Status').textContent='';
    });
  }

  if(document.readyState==='loading')
    document.addEventListener(
      'DOMContentLoaded',init,{once:true}
    );
  else init();
})();
