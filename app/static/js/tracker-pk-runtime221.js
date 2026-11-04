(() => {
  'use strict';

  const $=id=>document.getElementById(id);

  function init(){
    if(!$('pkRuntimeRun'))return;

    $('pkRuntimeRun').onclick=async()=>{
      try{
        const r=await fetch(
          '/pk/workspace/health/runtime',
          {cache:'no-store'}
        );

        if(!r.ok)
          throw Error('HTTP '+r.status);

        const d=await r.json();

        $('pkRuntimeStatus').textContent=
          'Running code: '+
          (d.code_commit||'unknown');

      }catch(e){
        $('pkRuntimeStatus').textContent=
          e.message;
      }
    };

    $('pkFastDiagnosticRun').onclick=async()=>{
      try{
        const r=await fetch(
          '/pk/workspace/health/fast-check?limit=100',
          {cache:'no-store'}
        );

        if(!r.ok)
          throw Error('HTTP '+r.status);

        const d=await r.json();

        $('pkRuntimeStatus').textContent=
          `SQL diagnostic: ${d.findings.length} finding(s), `+
          `${d.logs_checked} logs checked`+
          `${d.truncated?' (capped)':''}.`;

      }catch(e){
        $('pkRuntimeStatus').textContent=
          e.message;
      }
    };
  }

  if(document.readyState==='loading')
    document.addEventListener(
      'DOMContentLoaded',init,{once:true}
    );
  else init();
})();
