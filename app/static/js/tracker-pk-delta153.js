(() => {
  'use strict';

  const $=id=>document.getElementById(id);

  function init() {
    if(!$('pkDeltaRun'))return;

    let result=null;
    let seq=0;

    const choices=()=>[
      ...$('scenario').options
    ].filter(x=>x.value).map(x=>({
      id:x.value,
      label:x.textContent
    }));

    function reload() {
      const items=choices();

      for(const id of ['pkDeltaA','pkDeltaB']) {
        const select=$(id);
        const old=select.value;

        select.replaceChildren();
        select.add(
          new Option('Choose scenario','')
        );

        for(const item of items) {
          select.add(
            new Option(item.label,item.id)
          );
        }

        if(items.some(x=>x.id===old))
          select.value=old;
      }

      result=null;
      $('pkDeltaCsv').disabled=true;
    }

    const observer=new MutationObserver(reload);
    observer.observe(
      $('scenario'),
      {childList:true}
    );

    reload();

    async function execute() {
      const a=$('pkDeltaA').value;
      const b=$('pkDeltaB').value;

      if(!a||!b||a===b)
        throw Error(
          'Select two distinct saved scenarios'
        );

      const q=new URLSearchParams({
        compound_id:$('compound').value,
        scenario_a:a,
        scenario_b:b,
        days_back:$('back').value,
        days_forward:$('forward').value
      });

      const response=await fetch(
        '/pk/scenarios/delta?'+q,
        {cache:'no-store'}
      );

      if(!response.ok)
        throw Error(
          'HTTP '+response.status+': '+
          (await response.text()).slice(0,170)
        );

      return response.json();
    }

    function paint(data) {
      const canvas=$('pkDeltaPlot');
      const ctx=canvas.getContext('2d');
      const w=canvas.width;
      const h=canvas.height;

      ctx.clearRect(0,0,w,h);

      const nums=data.difference;
      if(nums.length<2)return;

      const max=Math.max(
        0.001,...nums.map(Math.abs)
      );

      const x=i=>
        65+(w-90)*i/(nums.length-1);

      const y=v=>
        h/2-v*((h-50)/2)/max;

      ctx.strokeStyle=
        getComputedStyle(document.documentElement)
        .getPropertyValue('--chart-grid').trim()
        ||'#888';

      ctx.beginPath();
      ctx.moveTo(65,h/2);
      ctx.lineTo(w-25,h/2);
      ctx.stroke();

      ctx.strokeStyle=
        getComputedStyle(document.documentElement)
        .getPropertyValue('--chart-planned').trim()
        ||'#b45309';

      ctx.lineWidth=2.5;
      ctx.beginPath();

      nums.forEach((v,i)=>
        i
          ?ctx.lineTo(x(i),y(v))
          :ctx.moveTo(x(i),y(v))
      );
      ctx.stroke();

      $('pkDeltaMetrics').textContent=
        'B minus A · Mean delta: '+
        window.TrackerNumber563.format(data.mean_delta)+
        ' mg-eq; AUC delta: '+
        data.auc_delta.toFixed(3)+
        ' mg-eq·h; range: '+
        data.min_delta.toFixed(3)+
        ' to '+
        data.max_delta.toFixed(3)+
        ' mg-eq. Model only.';
    }

    $('pkDeltaRun').onclick=async()=>{
      const n=++seq;

      $('pkDeltaMetrics').textContent=
        'Calculating modeled difference…';

      try {
        const r=await execute();

        if(n!==seq)return;

        result=r;
        paint(r);
        $('pkDeltaCsv').disabled=false;
      } catch(e) {
        if(n===seq) {
          result=null;
          $('pkDeltaCsv').disabled=true;
          $('pkDeltaMetrics').textContent=e.message;
        }
      }
    };

    $('pkDeltaCsv').onclick=()=>{
      if(!result)return;

      const safe=s=>{
        const v=String(s);
        return /^[=+@\-\t\r]/.test(v.trimStart())
          ?"'"+v
          :v;
      };

      const rows=[
        [
          'Time',
          'Modeled difference B - A (mg-eq)'
        ],
        ...result.at.map((at,i)=>[
          at,
          result.difference[i]
        ])
      ];

      const csv=rows.map(row=>
        row.map(x=>
          '"'+safe(x).replaceAll('"','""')+'"'
        ).join(',')
      ).join('\r\n');

      const url=URL.createObjectURL(
        new Blob(
          [csv],
          {type:'text/csv;charset=utf-8'}
        )
      );

      const link=document.createElement('a');
      link.href=url;
      link.download='tracker-pk-difference.csv';
      link.click();

      setTimeout(
        ()=>URL.revokeObjectURL(url),
        1000
      );
    };

    for(const id of ['pkDeltaA','pkDeltaB']) {
      $(id).addEventListener(
        'change',
        ()=>{
          $('pkDeltaCsv').disabled=true;
          result=null;
        }
      );
    }
  }

  if(document.readyState==='loading') {
    document.addEventListener(
      'DOMContentLoaded',init,{once:true}
    );
  } else init();
})();
