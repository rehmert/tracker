(() => {
  'use strict';
  function init(){
    const button=document.getElementById('pkOperationsRun');
    const text=document.getElementById('pkOperationsStatus');
    if(!button||!text)return;
    button.onclick=async()=>{
      button.disabled=true;text.textContent='Checking database integrity…';
      try{
        const r=await fetch('/pk/workspace/health/operations',{cache:'no-store'});
        if(!r.ok)throw Error('HTTP '+r.status);
        const data=await r.json();
        text.textContent='SQLite integrity: '+data.database_check+'; code: '+(data.code_commit||'unknown')+'. Backup verification: root-only logs.';
      }catch(e){text.textContent=e.message;}
      finally{button.disabled=false;}
    };
  }
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init,{once:true});else init();
})();
