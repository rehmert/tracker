(() => {
  'use strict';
  const $=id=>document.getElementById(id);
  function init(){
    if(!$('pkQualityCheck'))return;
    $('pkQualityCheck').onclick=async()=>{
      const node=$('pkQualityStatus');
      node.textContent='Checking hypothetical scenarios…';
      try{
        const r=await fetch('/pk/workspace/quality-report',{cache:'no-store'});
        if(!r.ok)throw Error('Quality check unavailable: '+r.status);
        const data=await r.json();
        node.textContent=data.scenarios_checked+' scenarios checked · '+data.findings.length+' findings. Read only.';
        const details=$('pkQualityFindings');details.replaceChildren();
        for(const finding of data.findings){
          const item=document.createElement('li');
          item.textContent=JSON.stringify(finding);
          details.append(item);
        }
      }catch(e){node.textContent=e.message;}
    };
  }
  if(document.readyState==='loading') document.addEventListener('DOMContentLoaded',init,{once:true});
  else init();
})();
