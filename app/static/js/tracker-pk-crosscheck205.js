(() => {
  'use strict';

  function init() {
    const button=document.getElementById('pkCrosscheckRun');
    const output=document.getElementById('pkCrosscheckStatus');

    if(!button||!output)return;

    button.onclick=async()=>{
      output.textContent='Checking read-only references…';

      try {
        const r=await fetch(
          '/pk/workspace/health/cross-module',
          {cache:'no-store'}
        );

        if(!r.ok)
          throw Error(
            'Diagnostic request failed: '+r.status
          );

        const data=await r.json();

        output.textContent=
          `${data.vials_checked} vials, `+
          `${data.logs_checked} logs, `+
          `${data.protocol_items_checked} protocol items checked; `+
          `${data.findings.length} findings.`;

        const list=document.getElementById(
          'pkCrosscheckFindings'
        );

        list.replaceChildren();

        for(const finding of data.findings) {
          const item=document.createElement('li');
          item.textContent=
            finding.type+' #'+finding.id;
          list.append(item);
        }
      } catch(e) {
        output.textContent=e.message;
      }
    };
  }

  if(document.readyState==='loading') {
    document.addEventListener(
      'DOMContentLoaded',init,{once:true}
    );
  } else init();
})();
